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
from typing import Optional, Tuple

from testflinger_agent.config import ATTACHMENTS_DIR
from testflinger_agent.errors import TFServerError
from testflinger_common.enums import TestEvent, TestPhase
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


class TestflingerJobPhase(ABC):
    """
    Represents a phase in a Testflinger job.
    """

    phase: TestPhase = None

    def __init__(self, job_data, client, rundir):
        self.client = client
        self.job_data = job_data
        self.rundir = rundir
        self.results_file = os.path.join(rundir, "testflinger-outcome.json")
        self.output_log = os.path.join(rundir, self.phase + ".log")
        self.serial_log = os.path.join(rundir, self.phase + "-serial.log")
        self.runner = CommandRunner(cwd=rundir, env=client.config)

    @abstractmethod
    def go(self) -> bool:
        """
        Return True if the phase should run or False otherwise
        """
        raise NotImplementedError

    @abstractmethod
    def register(self):
        """
        Perform all necessary registrations with the phase runner
        """
        raise NotImplementedError

    @abstractmethod
    def core(self) -> Tuple[int, Optional[TestEvent], str]:
        """
        Execute the "core" of the phase.

        Return [TODO]
        """
        raise NotImplementedError

    def post(self):
        """
        Execute any possible actions after the "core" of the phase
        """
        pass

    def run(self) -> Tuple[int, Optional[TestEvent], str]:
        """
        This is the generic structure of every phase
        """

        # check if the phase should actually run
        if not self.go():
            return 0, None, None

        # register the output handlers with the runner
        self.runner.register_output_handler(LogUpdateHandler(self.output_log))
        self.runner.register_output_handler(
            LiveOutputHandler(self.client, self.job_data["job_id"])
        )
        # perform additional runner registrations
        self.register()

        # display phase banner in the Testflinger output
        for line in self.banner(
            f"Starting testflinger {self.phase} phase "
            f"on {self.client.config.get('agent_id')}"
        ):
            self.runner.run(f"echo '{line}'")

        # run the "core" of the phase
        try:
            exitcode, exit_event, exit_reason = self.core()
        except Exception as exc:
            exit_event = f"{self.phase}_fail"
            exitcode = 100
            exit_reason = f"{type(exc).__name__}: {exc}"
            logger.exception(exit_reason)
        finally:
            self._update_results(exitcode)

        # perform any post-core actions
        self.post()

        return exitcode, exit_event, exit_reason

    def _update_results(self, exitcode):
        """Update the results file with the results of the specified phase

        :param exitcode:
            Exitcode from the device agent
        """
        with open(self.results_file, "r+") as results:
            outcome_data = json.load(results)
            outcome_data[self.phase + "_status"] = exitcode
            try:
                with open(self.output_log, "r+", encoding="utf-8") as logfile:
                    self._set_truncate(logfile)
                    outcome_data[self.phase + "_output"] = logfile.read()
            except FileNotFoundError:
                pass
            try:
                with open(
                    self.serial_log, "r+", encoding="utf-8", errors="ignore"
                ) as logfile:
                    self._set_truncate(logfile)
                    outcome_data[self.phase + "_serial"] = logfile.read()
            except FileNotFoundError:
                pass
            results.seek(0)
            json.dump(outcome_data, results)

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

    def banner(self, line):
        """Yield text lines to print a banner around a string

        :param line:
            Line of text to print a banner around
        """
        yield "*" * (len(line) + 4)
        yield "* {} *".format(line)
        yield "*" * (len(line) + 4)

    def _set_truncate(self, f, size=1024 * 1024):
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


class ExternalCommandPhase(TestflingerJobPhase):
    """
    Phases with a core executing an external command, specified in the config
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # retieve the external command to be executed
        self.cmd = self.client.config.get(self.phase + "_command")

    def go(self) -> bool:
        # the phase is "go" if the external command has been specified
        if not self.cmd:
            logger.info("No %s_command configured, skipping...", self.phase)
            return False
        return True

    def core(self) -> Tuple[int, Optional[TestEvent], str]:
        # execute the external command
        logger.info("Running %s_command: %s", self.phase, self.cmd)
        return self.runner.run(self.cmd)


class UnpackPhase(TestflingerJobPhase):

    phase = TestPhase.UNPACK

    # phases for which attachments are allowed
    supported_phases = (
        TestPhase.PROVISION, TestPhase.FIRMWARE_UPDATE, TestPhase.TEST
    )

    def register(self):
        self.runner.register_stop_condition_checker(
            GlobalTimeoutChecker(self.get_global_timeout())
        )

    def go(self) -> bool:
        if self.job_data.get("attachments_status") != "complete":
            # the phase is "go" if attachments have been provided
            logger.info(
                "No attachments provided in job data, skipping..."
            )
            return False
        return True

    def core(self) -> Tuple[int, Optional[TestEvent], str]:
        try:
            self.unpack_attachments(self.job_data)
        except Exception as error:
            # use the runner to display the error
            # (so that the output is also included in the phase results)
            for line in f"{type(error).__name__}: {error}".split('\n'):
                self.runner.run(f"echo '{line}'")
            # propagate the error (`run` uniformly handles fail cases)
            raise
        return 0, TestEvent.UNPACK_SUCCESS, None

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
            tuple(f"{phase}/" for phase in self.supported_phases)
        ):
            # trying to extract in an invalid folder, under the attachments folder
            raise tarfile.OutsideDestinationError(member, path)
        return tarfile.data_filter(member, path)

    def unpack_attachments(self, job_data: dict):
        """Download and unpack the attachments associated with a job"""
        job_id = job_data["job_id"]

        with tempfile.NamedTemporaryFile(suffix=".tar.gz") as archive_tmp:
            archive_path = Path(archive_tmp.name)
            # download attachment archive
            logger.info(f"Downloading attachments for {job_id}")
            self.client.get_attachments(job_id, path=archive_path)
            # extract archive into the attachments folder
            logger.info(f"Unpacking attachments for {job_id}")
            with tarfile.open(archive_path, "r:gz") as tar:
                tar.extractall(
                    Path(self.rundir) / ATTACHMENTS_DIR,
                    filter=self.secure_filter
                )

        # side effect: remove all attachment data from `job_data`
        # (so there is no interference with existing processes, especially
        # provisioning or firmware update, which are triggered when these
        # sections are not empty)
        for phase in self.supported_phases:
            phase_str = f"{phase}_data"
            try:
                phase_data = job_data[phase_str]
            except KeyError:
                pass
            else:
                # delete attachments, if they exist
                phase_data.pop("attachments", None)
                # it may be the case that attachments were the only data
                # included for this phase, so the phase can now be removed
                if not phase_data:
                    del job_data[phase_str]


class SetupPhase(ExternalCommandPhase):

    phase = TestPhase.SETUP

    def register(self):
        self.runner.register_stop_condition_checker(
            GlobalTimeoutChecker(self.get_global_timeout())
        )


class FirmwarePhase(ExternalCommandPhase):

    phase = TestPhase.FIRMWARE_UPDATE

    def go(self) -> bool:
        if not super().go():
            return False
        # the phase is "go" if the phase data has been provided
        if not self.job_data.get(f"{self.phase}_data"):
            logger.info(
                "No %s_data defined in job data, skipping...", self.phase
            )
            return False
        return True

    def register(self):
        self.runner.register_stop_condition_checker(
            GlobalTimeoutChecker(self.get_global_timeout())
        )


class ProvisionPhase(ExternalCommandPhase):

    phase = TestPhase.PROVISION

    def go(self) -> bool:
        if not super().go():
            return False
        # the phase is "go" if the phase data has been provided
        if not self.job_data.get(f"{self.phase}_data"):
            logger.info(
                "No %s_data defined in job data, skipping...", self.phase
            )
            return False
        return True

    def register(self):
        self.runner.register_stop_condition_checker(
            GlobalTimeoutChecker(self.get_global_timeout())
        )
        # Do not allow cancellation during provision for safety reasons
        self.runner.register_stop_condition_checker(
            JobCancelledChecker(self.client, self.job_data["job_id"])
        )


class TestCommandsPhase(ExternalCommandPhase):

    phase = TestPhase.TEST

    def go(self) -> bool:
        if not super().go():
            return False
        # the phase is "go" if the phase data has been provided
        if not self.job_data.get(f"{self.phase}_data"):
            logger.info(
                "No %s_data defined in job data, skipping...", self.phase
            )
            return False
        return True

    def register(self):
        self.runner.register_stop_condition_checker(
            GlobalTimeoutChecker(self.get_global_timeout())
        )
        # We only need to check for output timeouts during the test phase
        output_timeout_checker = OutputTimeoutChecker(
            self.get_output_timeout()
        )
        self.runner.register_stop_condition_checker(output_timeout_checker)
        self.runner.subscribe_event(
            RunnerEvents.OUTPUT_RECEIVED, output_timeout_checker.update
        )


class AllocatePhase(ExternalCommandPhase):

    phase = TestPhase.ALLOCATE

    def go(self) -> bool:
        if not super().go():
            return False
        # the phase is "go" if the phase data has been provided
        # (but no message is logged otherwise)
        if not self.job_data.get(f"{self.phase}_data"):
            return False
        return True

    def register(self):
        self.runner.register_stop_condition_checker(
            GlobalTimeoutChecker(self.get_global_timeout())
        )

    def post(self):
        """
        Read the json dict from "device-info.json" and send it to the server
        so that the multi-device agent can find the IP addresses of all
        subordinate jobs
        """
        device_info_file = os.path.join(self.rundir, "device-info.json")
        with open(device_info_file, "r") as f:
            device_info = json.load(f)

        # The allocated state MUST be reflected on the server or the multi-
        # device job can't continue
        while True:
            try:
                self.client.post_result(self.job_data["job_id"], device_info)
                break
            except TFServerError:
                logger.warning("Failed to post device_info, retrying...")
                time.sleep(60)

        self.client.post_job_state(self.job_data["job_id"], "allocated")
        self.wait_for_completion()

    def wait_for_completion(self):
        """Monitor the parent job and exit when it completes"""

        while True:
            try:
                this_job_state = self.client.check_job_state(
                    self.job_data["job_id"]
                )
                if this_job_state in ("complete", "completed", "cancelled"):
                    logger.info("This job completed, exiting...")
                    break

                parent_job_id = self.job_data.get("parent_job_id")
                if not parent_job_id:
                    logger.warning("No parent job ID found while allocated")
                    continue
                parent_job_state = self.client.check_job_state(
                    self.job_data.get("parent_job_id")
                )
                if parent_job_state in ("complete", "completed", "cancelled"):
                    logger.info("Parent job completed, exiting...")
                    break
            except TFServerError:
                logger.warning("Failed to get allocated job status, retrying")
            time.sleep(60)


class ReservePhase(ExternalCommandPhase):

    phase = TestPhase.RESERVE

    def go(self) -> bool:
        if not super().go():
            return False
        # the phase is "go" if the phase data has been provided
        # (but no message is logged otherwise)
        if not self.job_data.get(f"{self.phase}_data"):
            return False
        return True

    def register(self):
        # Reserve phase uses a separate timeout handler
        pass


class CleanupPhase(ExternalCommandPhase):

    phase = TestPhase.CLEANUP

    def register(self):
        self.runner.register_stop_condition_checker(
            GlobalTimeoutChecker(self.get_global_timeout())
        )


class TestflingerJob:

    phase_dict = {
        TestPhase.UNPACK: UnpackPhase,
        TestPhase.SETUP: SetupPhase,
        TestPhase.PROVISION: ProvisionPhase,
        TestPhase.FIRMWARE_UPDATE: FirmwarePhase,
        TestPhase.TEST: TestCommandsPhase,
        TestPhase.ALLOCATE: AllocatePhase,
        TestPhase.RESERVE: ReservePhase,
        TestPhase.CLEANUP: CleanupPhase,
    }

    def __init__(self, job_data, client, rundir):
        """
        :param job_data:
            Dictionary containing data for the test job_data
        :param client:
            Testflinger client object for communicating with the server
        :param rundir:
            Directory in which to run the command defined for the phase
        """
        self.job_data = job_data
        self.client = client
        self.rundir = rundir
        self.phase = "unknown"

    def run_test_phase(self, phase):
        """Run the specified test phase in rundir

        :param phase:
            Name of the test phase (setup, provision, test, ...)
        :return:
            Returncode from the command that was executed, 0 will be returned
            if there was no command to run
        """
        self.phase = phase
        phase_cls = self.phase_dict[phase]
        return phase_cls(self.job_data, self.client, self.rundir).run()


def set_nonblock(fd):
    """Set the specified fd to nonblocking output

    :param fd:
        File descriptor that should be set to nonblocking mode
    """

    # XXX: This is only used in one place right now, may want to consider
    # moving it if it gets wider use in the future
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
