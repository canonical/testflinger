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

import json
import logging
import os
import time

from testflinger_agent.errors import TFServerError
from typing import Optional

from .handlers import LiveOutputHandler, LogUpdateHandler
from .runner import CommandRunner, RunnerEvents
from .stop_condition_checkers import (
    GlobalTimeoutChecker,
    JobCancelledChecker,
    OutputTimeoutChecker,
)

logger = logging.getLogger(__name__)


class TestflingerJob:
    __test__ = False
    """This prevents pytest from trying to run this class as a test."""

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
        """Run the specified test phase in rundir.

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

        # Write the device information to the job /results endpoint
        device_info = self.get_device_info(rundir)

        try:
            self.client.post_result(self.job_id, device_info)
        except TFServerError:
            pass

        if not cmd:
            logger.info("No %s_command configured, skipping...", phase)
            return 0, None, None
        if phase in (
            "provision",
            "firmware_update",
            "test",
            "allocate",
            "reserve",
        ):
            if not self.job_data.get(f"{phase}_data"):
                logger.info(
                    "No %s_data defined in job data, skipping...", phase
                )
                return 0, None, None
            if self.job_data.get(f"{phase}_data", {}).get("skip", False):
                logger.info(
                    "Skipping %s phase as requested in job data", phase
                )
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
            # make sure the exit code is within the expected 0-255 range
            # (this also handles negative numbers)
            exitcode = exitcode % 256
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
        """Update the results file with the results of the specified phase.

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
        # the default for `output_bytes` when it is not explicitly set
        # in the agent config is specified in the config schema
        max_log_size = self.client.config["output_bytes"]
        with open(results_file, "r+") as results:
            outcome_data = json.load(results)
            if os.path.exists(output_log):
                outcome_data[phase + "_output"] = read_truncated(
                    output_log, size=max_log_size
                )
            if os.path.exists(serial_log):
                outcome_data[phase + "_serial"] = read_truncated(
                    serial_log, max_log_size
                )
            outcome_data[phase + "_status"] = exitcode
            results.seek(0)
            json.dump(outcome_data, results)

    def allocate_phase(self, rundir):
        """
        Read the json dict from "device-info.json" and send it to the server
        so that the multi-device agent can find the IP addresses of all
        subordinate jobs.
        """
        device_info = self.get_device_info(rundir)

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
        """Monitor the parent job and exit when it completes."""
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

    def get_global_timeout(self):
        """Get the global timeout for the test run in seconds."""
        # Default timeout is 4 hours
        default_timeout = 4 * 60 * 60

        # Don't exceed the maximum timeout configured for the device!
        return min(
            self.job_data.get("global_timeout", default_timeout),
            self.client.config.get("global_timeout", default_timeout),
        )

    def get_output_timeout(self):
        """Get the output timeout for the test run in seconds."""
        # Default timeout is 15 minutes
        default_timeout = 15 * 60

        # Don't exceed the maximum timeout configured for the device!
        return min(
            self.job_data.get("output_timeout", default_timeout),
            self.client.config.get("output_timeout", default_timeout),
        )

    def banner(self, line):
        """Yield text lines to print a banner around a sting.

        :param line:
            Line of text to print a banner around
        """
        yield "*" * (len(line) + 4)
        yield "* {} *".format(line)
        yield "*" * (len(line) + 4)

    def get_device_info(self, rundir: str) -> Optional[dict]:
        """Read the json dict from "device-info.json" with information
        about the device associated with an agent.

        :param rundir: String with the directory on where to locate the file
        :return: Device information from device-info.json
        """
        if rundir:
            try:
                device_info_file = os.path.join(rundir, "device-info.json")
                with open(device_info_file, "r") as f:
                    device_info = json.load(f)
                return device_info
            except FileNotFoundError:
                return None

        return None


def read_truncated(filename: str, size: int) -> str:
    """Return a string corresponding to the last bytes of a text file.

    Include a warning message at the end of the returned value if the file
    has been truncated.

    :param filename:
        The name of the text file
    :param size:
        Maximum number of bytes to be read from the end of the file
        (overrides default `output_bytes` value in the agent config)
    """
    with open(filename, "r", encoding="utf-8", errors="ignore") as file:
        end = file.seek(0, 2)
        if end > size:
            file.seek(end - size, 0)
            return file.read() + (
                f"\nWARNING: File truncated to its last {size} bytes!"
            )
        file.seek(0, 0)
        return file.read()
