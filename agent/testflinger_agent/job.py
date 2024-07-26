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

import fcntl
import json
import logging
import os
import time

from testflinger_agent.errors import TFServerError
from .runner import CommandRunner, RunnerEvents
from .handlers import LiveOutputHandler, LogUpdateHandler
from .stop_condition_checkers import (
    JobCancelledChecker,
    GlobalTimeoutChecker,
    OutputTimeoutChecker,
)

logger = logging.getLogger(__name__)


class TestflingerJob:
    def __init__(self, job_data, client):
        """
        :param job_data:
            Dictionary containing data for the test job_data
        :param client:
            Testflinger client object for communicating with the server
        """
        self.client = client
        self.job_data = job_data
        self.job_id = job_data.get("job_id")
        self.phase = "unknown"

    def run_test_phase(self, phase, rundir):
        """Run the specified test phase in rundir

        :param phase:
            Name of the test phase (setup, provision, test, ...)
        :param rundir:
            Directory in which to run the command defined for the phase
        :return:
            Returncode from the command that was executed, 0 will be returned
            if there was no command to run
        """
        self.phase = phase
        cmd = self.client.config.get(phase + "_command")
        node = self.client.config.get("agent_id")
        if not cmd:
            logger.info("No %s_command configured, skipping...", phase)
            return 0, None, None
        if phase == "provision" and not self.job_data.get("provision_data"):
            logger.info("No provision_data defined in job data, skipping...")
            return 0, None, None
        if phase == "firmware_update" and not self.job_data.get(
            "firmware_update_data"
        ):
            logger.info(
                "No firmware_update_data defined in job data, skipping..."
            )
            return 0, None, None
        if phase == "test" and not self.job_data.get("test_data"):
            logger.info("No test_data defined in job data, skipping...")
            return 0, None, None
        if phase == "allocate" and not self.job_data.get("allocate_data"):
            return 0, None, None
        if phase == "reserve" and not self.job_data.get("reserve_data"):
            return 0, None, None
        results_file = os.path.join(rundir, "testflinger-outcome.json")
        output_log = os.path.join(rundir, phase + ".log")
        serial_log = os.path.join(rundir, phase + "-serial.log")

        logger.info("Running %s_command: %s", phase, cmd)
        runner = CommandRunner(cwd=rundir, env=self.client.config)
        output_log_handler = LogUpdateHandler(output_log)
        live_output_handler = LiveOutputHandler(self.client, self.job_id)
        runner.register_output_handler(output_log_handler)
        runner.register_output_handler(live_output_handler)

        # Reserve phase uses a separate timeout handler
        if phase != "reserve":
            global_timeout_checker = GlobalTimeoutChecker(
                self.get_global_timeout()
            )
            runner.register_stop_condition_checker(global_timeout_checker)

        # We only need to check for output timeouts during the test phase
        if phase == "test":
            output_timeout_checker = OutputTimeoutChecker(
                self.get_output_timeout()
            )
            runner.register_stop_condition_checker(output_timeout_checker)
            runner.subscribe_event(
                RunnerEvents.OUTPUT_RECEIVED, output_timeout_checker.update
            )

        # Do not allow cancellation during provision for safety reasons
        if phase != "provision":
            job_cancelled_checker = JobCancelledChecker(
                self.client, self.job_id
            )
            runner.register_stop_condition_checker(job_cancelled_checker)

        for line in self.banner(
            "Starting testflinger {} phase on {}".format(phase, node)
        ):
            runner.run(f"echo '{line}'")
        try:
            # Set exit_event to fail for this phase in case of an exception
            exit_event = f"{phase}_fail"
            exitcode, exit_event, exit_reason = runner.run(cmd)
        except Exception as exc:
            logger.exception(exc)
            exitcode = 100
            exit_reason = str(exc)  # noqa: F841 - ignore this until it's used
        finally:
            self._update_phase_results(
                results_file, phase, exitcode, output_log, serial_log
            )
        if phase == "allocate":
            self.allocate_phase(rundir)
        return exitcode, exit_event, exit_reason

    def _update_phase_results(
        self, results_file, phase, exitcode, output_log, serial_log
    ):
        """Update the results file with the results of the specified phase

        :param results_file:
            Path to the results file
        :param phase:
            Name of the phase
        :param exitcode:
            Exitcode from the device agent
        :param output_log:
            Path to the output log file
        :param serial_log:
            Path to the serial log file
        """
        with open(results_file, "r+") as results:
            outcome_data = json.load(results)
            if os.path.exists(output_log):
                with open(output_log, "r+", encoding="utf-8") as logfile:
                    self._set_truncate(logfile)
                    outcome_data[phase + "_output"] = logfile.read()
            if os.path.exists(serial_log):
                with open(serial_log, "r+", encoding="utf-8") as logfile:
                    self._set_truncate(logfile)
                    outcome_data[phase + "_serial"] = logfile.read()
            outcome_data[phase + "_status"] = exitcode
            results.seek(0)
            json.dump(outcome_data, results)

    def allocate_phase(self, rundir):
        """
        Read the json dict from "device-info.json" and send it to the server
        so that the multi-device agent can find the IP addresses of all
        subordinate jobs
        """
        device_info_file = os.path.join(rundir, "device-info.json")
        with open(device_info_file, "r") as f:
            device_info = json.load(f)

        # The allocated state MUST be reflected on the server or the multi-
        # device job can't continue
        while True:
            try:
                self.client.post_result(self.job_id, device_info)
                break
            except TFServerError:
                logger.warning("Failed to post device_info, retrying...")
                time.sleep(60)

        self.client.post_job_state(self.job_id, "allocated")

        self.wait_for_completion()

    def wait_for_completion(self):
        """Monitor the parent job and exit when it completes"""

        while True:
            try:
                this_job_state = self.client.check_job_state(self.job_id)
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
        """Yield text lines to print a banner around a sting

        :param line:
            Line of text to print a banner around
        """
        yield "*" * (len(line) + 4)
        yield "* {} *".format(line)
        yield "*" * (len(line) + 4)


def set_nonblock(fd):
    """Set the specified fd to nonblocking output

    :param fd:
        File descriptor that should be set to nonblocking mode
    """

    # XXX: This is only used in one place right now, may want to consider
    # moving it if it gets wider use in the future
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
