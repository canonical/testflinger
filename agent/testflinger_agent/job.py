# Copyright (C) 2017-2024 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

from abc import ABC, abstractmethod
import fcntl
import json
import logging
import os
from pathlib import Path
import tempfile
import time
from typing import Optional, NamedTuple

from testflinger_agent.client import TestflingerClient
from testflinger_agent.config import ATTACHMENTS_DIR
from testflinger_agent.errors import TFServerError
from testflinger_agent.event_emitter import EventEmitter
from testflinger_common.enums import TestEvent, TestPhase, JobState
from .runner import CommandRunner, RunnerEvents
from .handlers import LiveOutputHandler, LogUpdateHandler
from .stop_condition_checkers import (
    JobCancelledChecker,
    GlobalTimeoutChecker,
    OutputTimeoutChecker,
)

try:
    # attempt importing a tarfile filter, to check if filtering is supported
    from tarfile import data_filter

    del data_filter
except ImportError:
    # import a patched version of `tarfile` that supports filtering;
    # this conditional import can be removed when all agents run
    # versions of Python that support filtering, i.e. at least:
    # 3.8.17, 3.9.17, 3.10.12, 3.11.4, 3.12
    from . import tarfile_patch as tarfile
else:
    import tarfile


logger = logging.getLogger(__name__)


class TestflingerJobParameters(NamedTuple):
    """The bundle of data required (and shared) by a job and its phases"""

    job_data: dict
    client: TestflingerClient
    rundir: Path

    def get_global_timeout(self):
        """Get the global timeout for the test run in seconds"""
        # Default timeout is 4 hours
        default_timeout = 4 * 60 * 60

        # Don't exceed the maximum timeout configured for the device!
        return min(
            self.job_data.get("global_timeout", default_timeout),
            self.client.config.get("global_timeout", default_timeout),
        )

    def get_output_timeout(self):
        """Get the output timeout for the test run in seconds"""
        # Default timeout is 15 minutes
        default_timeout = 15 * 60

        # Don't exceed the maximum timeout configured for the device!
        return min(
            self.job_data.get("output_timeout", default_timeout),
            self.client.config.get("output_timeout", default_timeout),
        )


class JobPhaseResult(NamedTuple):
    """The bundle of data holding the results of a phase"""

    exit_code: Optional[int] = None
    event: Optional[TestEvent] = None
    detail: Optional[str] = None


class JobPhase(ABC):
    """
    A phase in a Testflinger job

    This is an abstract class that captures the interface and basic
    functionality of a phase.
    """

    # Classes derived from JobPhase are associated with a TestPhase id
    phase_id: TestPhase = None

    def __init_subclass__(subcls, phase_id: Optional[TestPhase] = None):
        if subcls is not None:
            subcls.phase_id = phase_id

    def __init__(self, params: TestflingerJobParameters):
        self.params = params
        # phase-specific files
        self.results_file = params.rundir / "testflinger-outcome.json"
        self.output_log = params.rundir / f"{self.phase_id}.log"
        self.serial_log = params.rundir / f"{self.phase_id}-serial.log"
        # phase-specific runner (for executing commands in the rundir)
        self.runner = CommandRunner(
            cwd=params.rundir, env=params.client.config
        )
        # phase result: initially empty, set later by `JobPhase.run`
        self.result: Optional[JobPhaseResult] = None

    @abstractmethod
    def go(self) -> bool:
        """Return True if the phase should run or False if skipping"""
        raise NotImplementedError

    @abstractmethod
    def register(self):
        """Perform all necessary registrations with the phase runner"""
        raise NotImplementedError

    @abstractmethod
    def run_core(self) -> JobPhaseResult:
        """Execute the "core" of the phase"""
        raise NotImplementedError

    def process_results(self):
        """Execute any possible actions after the "core" of the phase"""
        pass

    def run(self):
        """This is the generic structure of every phase"""

        assert self.go()

        # register the output handlers with the runner
        self.runner.register_output_handler(LogUpdateHandler(self.output_log))
        self.runner.register_output_handler(
            LiveOutputHandler(
                self.params.client, self.params.job_data["job_id"]
            )
        )
        # perform additional runner registrations
        self.register()

        # display phase banner in the Testflinger output
        for line in self.banner(
            f"Starting testflinger {self.phase_id} phase "
            f"on {self.params.client.config.get('agent_id')}"
        ):
            self.runner.run(f"echo '{line}'")

        # run the "core" of the phase and store the result
        self.result = self.run_core()

        # perform any post-core actions
        self.process_results()
        self.update_results_file()

    def update_results_file(self):
        """Update the results file with the results of this phase"""
        with open(self.results_file, "r+") as results:
            outcome_data = json.load(results)
            outcome_data[f"{self.phase_id}_status"] = self.result.exit_code
            try:
                with open(self.output_log, "r+", encoding="utf-8") as logfile:
                    set_truncate(logfile)
                    outcome_data[f"{self.phase_id}_output"] = logfile.read()
            except FileNotFoundError:
                pass
            try:
                with open(
                    self.serial_log, "r+", encoding="utf-8", errors="ignore"
                ) as logfile:
                    set_truncate(logfile)
                    outcome_data[f"{self.phase_id}_serial"] = logfile.read()
            except FileNotFoundError:
                pass
            results.seek(0)
            json.dump(outcome_data, results)

    def banner(self, line):
        """Yield text lines to print a banner around a string

        :param line:
            Line of text to print a banner around
        """
        yield "*" * (len(line) + 4)
        yield "* {} *".format(line)
        yield "*" * (len(line) + 4)


class ExternalCommandPhase(JobPhase):
    """
    Phases with a core executing an external command, specified in the config
    """

    def __init__(self, params: TestflingerJobParameters):
        super().__init__(params)
        # retieve the external command to be executed
        self.cmd = self.params.client.config.get(self.phase_id + "_command")

    def go(self) -> bool:
        # the phase is "go" if the external command has been specified
        if not self.cmd:
            logger.info("No %s_command configured, skipping...", self.phase_id)
            return False
        return True

    def run_core(self) -> JobPhaseResult:
        # execute the external command
        logger.info("Running %s_command: %s", self.phase_id, self.cmd)
        try:
            exit_code, event, detail = self.runner.run(self.cmd)
            if exit_code == 0:
                # complete, successful run
                return JobPhaseResult(
                    exit_code=exit_code,
                    event=f"{self.phase_id}_success",
                )
            else:
                # [NOTE] This is a deviation from the current approach
                # where a separate event is emitted when stop events are
                # returned from the runner and then a fail event on top
                # Here we *only* emit the stop event
                # self.emitter.emit_event(event, detail)
                if event:
                    return JobPhaseResult(
                        exit_code=exit_code,
                        event=event,
                        detail=detail,
                    )
                else:
                    return JobPhaseResult(
                        exit_code=exit_code,
                        event=f"{self.phase_id}_fail",
                        detail=self.parse_error_logs(),
                    )
        except Exception as error:
            # failed phase run due to an exception
            detail = f"{type(error).__name__}: {error}"
            logger.exception(detail)
            return JobPhaseResult(
                exit_code=100,
                event=f"{self.phase_id}_fail",
                detail=detail,
            )

    def parse_error_logs(self):
        # [TODO] Move filenames used to pass information to the common module
        with open(
            self.params.rundir / "device-connector-error.json", "r"
        ) as error_file:
            error_file_contents = error_file.read()
            try:
                exception_info = json.loads(error_file_contents)[
                    f"{self.phase_id}_exception_info"
                ]
                if exception_info["exception_cause"] is None:
                    detail = "%s: %s" % (
                        exception_info["exception_name"],
                        exception_info["exception_message"],
                    )
                else:
                    detail = "%s: %s caused by %s" % (
                        exception_info["exception_name"],
                        exception_info["exception_message"],
                        exception_info["exception_cause"],
                    )
                return detail
            except (json.JSONDecodeError, KeyError):
                # [TODO] When do these errors arise?
                return ""


class SetupPhase(ExternalCommandPhase, phase_id=TestPhase.SETUP):

    def register(self):
        self.runner.register_stop_condition_checker(
            GlobalTimeoutChecker(self.params.get_global_timeout())
        )


class FirmwarePhase(ExternalCommandPhase, phase_id=TestPhase.FIRMWARE_UPDATE):

    def go(self) -> bool:
        if not super().go():
            return False
        # the phase is "go" if the phase data has been provided
        if not self.params.job_data.get(f"{self.phase_id}_data"):
            logger.info(
                "No %s_data defined in job data, skipping...", self.phase_id
            )
            return False
        return True

    def register(self):
        self.runner.register_stop_condition_checker(
            GlobalTimeoutChecker(self.params.get_global_timeout())
        )


class ProvisionPhase(ExternalCommandPhase, phase_id=TestPhase.PROVISION):

    def go(self) -> bool:
        if not super().go():
            return False
        # the phase is "go" if the phase data has been provided
        if not self.params.job_data.get(f"{self.phase_id}_data"):
            logger.info(
                "No %s_data defined in job data, skipping...", self.phase_id
            )
            return False
        return True

    def register(self):
        self.runner.register_stop_condition_checker(
            GlobalTimeoutChecker(self.params.get_global_timeout())
        )
        # Do not allow cancellation during provision for safety reasons
        self.runner.register_stop_condition_checker(
            JobCancelledChecker(
                self.params.client, self.params.job_data["job_id"]
            )
        )

    def process_results(self):
        if self.result.exit_code == 46:
            # exit code 46 is our indication that recovery failed!
            # In this case, we need to mark the device offline
            self.result = self.result._replace(event=TestEvent.RECOVERY_FAIL)

        self.params.client.post_provision_log(
            self.params.job_data["job_id"],
            self.result.exit_code,
            self.result.event,
        )


class TestCommandsPhase(ExternalCommandPhase, phase_id=TestPhase.TEST):

    def go(self) -> bool:
        if not super().go():
            return False
        # the phase is "go" if the phase data has been provided
        if not self.params.job_data.get(f"{self.phase_id}_data"):
            logger.info(
                "No %s_data defined in job data, skipping...", self.phase_id
            )
            return False
        return True

    def register(self):
        self.runner.register_stop_condition_checker(
            GlobalTimeoutChecker(self.params.get_global_timeout())
        )
        # We only need to check for output timeouts during the test phase
        output_timeout_checker = OutputTimeoutChecker(
            self.params.get_output_timeout()
        )
        self.runner.register_stop_condition_checker(output_timeout_checker)
        self.runner.subscribe_event(
            RunnerEvents.OUTPUT_RECEIVED, output_timeout_checker.update
        )


class AllocatePhase(ExternalCommandPhase, phase_id=TestPhase.ALLOCATE):

    def go(self) -> bool:
        if not super().go():
            return False
        # the phase is "go" if the phase data has been provided
        # (but no message is logged otherwise)
        if not self.params.job_data.get(f"{self.phase_id}_data"):
            return False
        return True

    def register(self):
        self.runner.register_stop_condition_checker(
            GlobalTimeoutChecker(self.params.get_global_timeout())
        )

    def process_results(self):
        """
        Read the json dict from "device-info.json" and send it to the server
        so that the multi-device agent can find the IP addresses of all
        subordinate jobs
        """
        device_info_file = self.params.rundir / "device-info.json"
        with open(device_info_file, "r") as f:
            device_info = json.load(f)

        # The allocated state MUST be reflected on the server or the multi-
        # device job can't continue
        while True:
            try:
                self.params.client.post_result(
                    self.params.job_data["job_id"], device_info
                )
                break
            except TFServerError:
                logger.warning("Failed to post device_info, retrying...")
                time.sleep(60)

        self.params.client.post_job_state(
            self.params.job_data["job_id"], JobState.ALLOCATED
        )
        self.wait_for_completion()

    def wait_for_completion(self):
        """Monitor the parent job and exit when it completes"""

        while True:
            try:
                this_job_state = self.params.client.check_job_state(
                    self.params.job_data["job_id"]
                )
                if this_job_state in (
                    "complete",
                    JobState.COMPLETED,
                    JobState.CANCELLED,
                ):
                    logger.info("This job completed, exiting...")
                    break

                parent_job_id = self.params.job_data.get("parent_job_id")
                if not parent_job_id:
                    logger.warning("No parent job ID found while allocated")
                    continue
                parent_job_state = self.params.client.check_job_state(
                    self.params.job_data.get("parent_job_id")
                )
                if parent_job_state in (
                    "complete",
                    JobState.COMPLETED,
                    JobState.CANCELLED,
                ):
                    logger.info("Parent job completed, exiting...")
                    break
            except TFServerError:
                logger.warning("Failed to get allocated job status, retrying")
            time.sleep(60)


class ReservePhase(ExternalCommandPhase, phase_id=TestPhase.RESERVE):

    def go(self) -> bool:
        if not super().go():
            return False
        # the phase is "go" if the phase data has been provided
        # (but no message is logged otherwise)
        if not self.params.job_data.get(f"{self.phase_id}_data"):
            return False
        return True

    def register(self):
        # Reserve phase uses a separate timeout handler
        pass


class CleanupPhase(ExternalCommandPhase, phase_id=TestPhase.CLEANUP):

    def register(self):
        self.runner.register_stop_condition_checker(
            GlobalTimeoutChecker(self.params.get_global_timeout())
        )


class TestflingerJob:

    phase_sequence = (
        TestPhase.SETUP,
        TestPhase.PROVISION,
        TestPhase.FIRMWARE_UPDATE,
        TestPhase.TEST,
        TestPhase.ALLOCATE,
        TestPhase.RESERVE,
    )

    phase_cls_map = {
        TestPhase.SETUP: SetupPhase,
        TestPhase.PROVISION: ProvisionPhase,
        TestPhase.FIRMWARE_UPDATE: FirmwarePhase,
        TestPhase.TEST: TestCommandsPhase,
        TestPhase.ALLOCATE: AllocatePhase,
        TestPhase.RESERVE: ReservePhase,
        TestPhase.CLEANUP: CleanupPhase,
    }

    def __init__(self, job_data: dict, client: TestflingerClient):
        """
        :param job_data:
            Dictionary containing data for the test job_data
        :param client:
            Testflinger client object for communicating with the server
        :param rundir:
            Directory in which to run the command defined for the phase
        """
        self.job_id = job_data["job_id"]

        rundir = Path(client.config.get("execution_basedir")) / self.job_id
        rundir.mkdir()
        # specify directories and result files
        # Dump the job data to testflinger.json in our execution dir
        with open(rundir / "testflinger.json", "w") as f:
            json.dump(job_data, f)
        # Create json outcome file where phases will store their output
        with open(rundir / "testflinger-outcome.json", "w") as f:
            json.dump({}, f)
        # Clear error log before starting
        with open(rundir / "device-connector-error.json", "w") as f:
            pass

        # bundle all necessary job parameters into `self.params` so that
        # the job phases are only passed a single reference
        self.params = TestflingerJobParameters(job_data, client, Path(rundir))
        self.current_phase = None
        self.end_phase = None
        self.end_reason = TestEvent.NORMAL_EXIT
        self.emitter = EventEmitter(
            job_data["job_queue"],
            job_data.get("job_status_webhook"),
            client,
            job_data["job_id"],
        )
        self.phases = {
            phase_id: phase_cls(self.params)
            for phase_id, phase_cls in self.phase_cls_map.items()
        }

    def start(self):
        logger.info("Starting job %s", self.job_id)
        self.emitter.emit_event(
            TestEvent.JOB_START,
            f"{self.params.client.server}/jobs/{self.job_id}",
        )

    def check_end(self) -> bool:
        phase = self.phases[self.current_phase]
        if phase.result.exit_code and self.current_phase != TestPhase.TEST:
            logger.debug("Phase %s failed, aborting job" % phase)
            # set these here because self.end() is called after cleanup
            self.end_phase = phase.phase_id
            self.end_reason = phase.result.event
            return True
        return False

    def end(self):
        logger.info("Ending job %s", self.job_id)
        self.emitter.emit_event(TestEvent.JOB_END, self.end_reason)

    def check_cancel(self) -> bool:
        return (
            self.params.client.check_job_state(self.job_id)
            == JobState.CANCELLED
        )

    def cancel(self):
        logger.info("Job cancellation was requested, exiting.")
        self.emitter.emit_event(TestEvent.CANCELLED)

    def go(self, phase_id: TestPhase) -> bool:
        return self.phases[phase_id].go()

    def run(self, phase_id: TestPhase) -> JobPhaseResult:
        """Run the specified test phase

        :param phase:
            Name of the test phase (setup, provision, test, ...)
        """
        self.current_phase = phase_id
        self.params.client.post_job_state(self.job_id, phase_id)
        self.emitter.emit_event(TestEvent(f"{phase_id}_start"))
        phase = self.phases[phase_id]
        phase.run()
        # self.params.client.post_influx(phase.id, phase.result.exit_code)
        self.emitter.emit_event(phase.result.event, phase.result.detail)
        return phase.result

    def secure_filter(self, member, path):
        """Combine the `data` filter with custom attachment filtering

        Makes sure that the starting folder for all attachments coincides
        with one of the supported phases, i.e. that the attachment archive
        has been created properly and no attachment will be extracted to an
        unexpected location.
        """
        try:
            resolved = Path(member.name).resolve().relative_to(Path.cwd())
        except ValueError as error:
            # essentially trying to extract higher than the attachments folder
            raise tarfile.OutsideDestinationError(member, path) from error
        if not str(resolved).startswith(
            tuple(
                f"{phase}/"
                for phase in (
                    TestPhase.PROVISION,
                    TestPhase.FIRMWARE_UPDATE,
                    TestPhase.TEST,
                )
            )
        ):
            # trying to extract in invalid folder under the attachments folder
            raise tarfile.OutsideDestinationError(member, path)
        return tarfile.data_filter(member, path)

    def check_attachments(self) -> bool:
        return self.params.job_data.get("attachments_status") == "complete"

    def unpack_attachments(self):
        """Download and unpack the attachments associated with a job"""

        with tempfile.NamedTemporaryFile(suffix=".tar.gz") as archive_tmp:
            archive_path = Path(archive_tmp.name)
            # download attachment archive
            logger.info(f"Downloading attachments for {self.job_id}")
            self.params.client.get_attachments(self.job_id, path=archive_path)
            # extract archive into the attachments folder
            logger.info(f"Unpacking attachments for {self.job_id}")
            with tarfile.open(archive_path, "r:gz") as tar:
                tar.extractall(
                    self.params.rundir / ATTACHMENTS_DIR,
                    filter=self.secure_filter,
                )

        # side effect: remove all attachment data from `self.params.job_data`
        # (so there is no interference with existing processes, especially
        # provisioning or firmware update, which are triggered when these
        # sections are not empty)
        for phase in self.supported_phases:
            phase_str = f"{phase}_data"
            try:
                phase_data = self.params.job_data[phase_str]
            except KeyError:
                pass
            else:
                # delete attachments, if they exist
                phase_data.pop("attachments", None)
                # it may be the case that attachments were the only data
                # included for this phase, so the phase can now be removed
                if not phase_data:
                    del self.params.job_data[phase_str]


def set_nonblock(fd):
    """Set the specified fd to nonblocking output

    :param fd:
        File descriptor that should be set to nonblocking mode
    """

    # XXX: This is only used in one place right now, may want to consider
    # moving it if it gets wider use in the future
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)


def set_truncate(f, size=1024 * 1024):
    """Set up an open file so that we don't read more than a specified
        size. We want to read from the end of the file rather than the
        beginning. Write a warning at the end of the file if it was too big.

    :param f:
        The file object, which should be opened for read/write
    :param size:
        Maximum number of bytes we want to allow from reading the file
    """
    end = f.seek(0, 2)
    if end > size:
        f.write("\nWARNING: File has been truncated due to length!")
        f.seek(end - size, 0)
    else:
        f.seek(0, 0)
