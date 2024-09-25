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
import time

from testflinger_agent.errors import TFServerError
from testflinger_common.enums import TestPhase
from .runner import CommandRunner, RunnerEvents
from .handlers import LiveOutputHandler, LogUpdateHandler
from .stop_condition_checkers import (
    JobCancelledChecker,
    GlobalTimeoutChecker,
    OutputTimeoutChecker,
)

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
    def core(self):
        """
        Execute the "core" of the phase.
        """
        raise NotImplementedError

    def post(self):
        """
        Execute any possible actions after the "core" of the phase
        """
        pass

    def run(self):
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
            logger.exception(exc)
            exit_event = f"{self.phase}_fail"
            exitcode = 100
            exit_reason = str(exc)  # noqa: F841 - ignore this until it's used
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

    def core(self):
        # execute the external command
        logger.info("Running %s_command: %s", self.phase, self.cmd)
        return self.runner.run(self.cmd)


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
