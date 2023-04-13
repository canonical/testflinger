# Copyright (C) 2017 Canonical
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
import signal
import sys
import subprocess
import time

from testflinger_agent.errors import TFServerError

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
            return 0
        if phase == "provision" and not self.job_data.get("provision_data"):
            logger.info("No provision_data defined in job data, skipping...")
            return 0
        if phase == "test" and not self.job_data.get("test_data"):
            logger.info("No test_data defined in job data, skipping...")
            return 0
        if phase == "allocate" and not self.job_data.get("allocate_data"):
            return 0
        if phase == "reserve" and not self.job_data.get("reserve_data"):
            return 0
        results_file = os.path.join(rundir, "testflinger-outcome.json")
        output_log = os.path.join(rundir, phase + ".log")
        serial_log = os.path.join(rundir, phase + "-serial.log")
        logger.info("Running %s_command: %s", phase, cmd)
        # Set the exitcode to some failed status in case we get interrupted
        exitcode = 99

        for line in self.banner(
            "Starting testflinger {} phase on {}".format(phase, node)
        ):
            self.run_with_log("echo '{}'".format(line), output_log, rundir)
        try:
            exitcode = self.run_with_log(cmd, output_log, rundir)
        except Exception as e:
            logger.exception(e)
        finally:
            self._update_phase_results(
                results_file, phase, exitcode, output_log, serial_log
            )
        if phase == "allocate":
            self.allocate_phase(rundir)
        return exitcode

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
        # For now, we don't have to monitor our own job state, since the
        # another thread monitors it. But if this changes, we'll need to watch
        # for changes to our own job state

        while True:
            try:
                parent_job_state = self.client.check_job_state(
                    self.job_data.get("parent_job_id")
                )
                if parent_job_state in ("completed", "cancelled"):
                    logger.info("Parent job completed, exiting...")
                    break
            except TFServerError:
                logger.warning("Failed to get parent job, retrying...")
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

    def run_with_log(self, cmd, logfile, cwd=None):
        """Execute command in a subprocess and log the output

        :param cmd:
            Command to run
        :param logfile:
            Filename to save the output in
        :param cwd:
            Path to run the command from
        :return:
            returncode from the process
        """
        env = os.environ.copy()
        # Make sure there all values we add are strings
        env.update(
            {k: v for k, v in self.client.config.items() if isinstance(v, str)}
        )
        global_timeout = self.get_global_timeout()
        output_timeout = self.get_output_timeout()
        start_time = time.time()
        with open(logfile, "a", encoding="utf-8") as f:
            live_output_buffer = ""
            buffer_timeout = time.time()
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=True,
                cwd=cwd,
                env=env,
            )

            def cleanup(signum, frame):
                process.kill()

            signal.signal(signal.SIGTERM, cleanup)
            set_nonblock(process.stdout.fileno())

            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    # Process exited
                    break

                if line:
                    # Write the latest output to the log file, stdout, and
                    # the live output buffer
                    buf = line.decode(sys.stdout.encoding, errors="replace")
                    sys.stdout.write(buf)
                    live_output_buffer += buf
                    f.write(buf)
                    f.flush()
                else:
                    if (
                        self.phase == "test"
                        and time.time() - buffer_timeout > output_timeout
                    ):
                        buf = (
                            "\nERROR: Output timeout reached! "
                            "({}s)\n".format(output_timeout)
                        )
                        live_output_buffer += buf
                        f.write(buf)
                        process.kill()
                        break

                # Check if it's time to send the output buffer to the server
                if live_output_buffer and time.time() - buffer_timeout > 10:
                    if self.client.post_live_output(
                        self.job_id, live_output_buffer
                    ):
                        live_output_buffer = ""
                        buffer_timeout = time.time()

                # Check global timeout
                if (
                    self.phase != "reserve"
                    and time.time() - start_time > global_timeout
                ):
                    buf = "\nERROR: Global timeout reached! ({}s)\n".format(
                        global_timeout
                    )
                    live_output_buffer += buf
                    f.write(buf)
                    process.kill()
                    break

                # Check if job was canceled
                if (
                    self.client.check_job_state(self.job_id) == "cancelled"
                    and self.phase != "provision"
                ):
                    logger.info("Job cancellation was requested, exiting.")
                    process.kill()
                    break

            if live_output_buffer:
                self.client.post_live_output(self.job_id, live_output_buffer)

            try:
                status = process.wait(10)  # process.returncode
            except TimeoutError:
                status = 99  # Default in case something goes wrong
            return status

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
