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

import json
import logging
import os
import shutil
import signal
import sys

from testflinger_agent.job import TestflingerJob
from testflinger_agent.errors import TFServerError
from testflinger_agent.event_emitter import EventEmitter
from testflinger_common.enums import JobState, TestPhase, TestEvent


logger = logging.getLogger(__name__)


def parse_error_logs(error_log_path: str, phase: str):
    with open(error_log_path, "r") as error_file:
        error_file_contents = error_file.read()
        try:
            exception_info = json.loads(error_file_contents)[
                f"{phase}_exception_info"
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
            return ""


class TestflingerAgent:
    def __init__(self, client):
        self.client = client
        signal.signal(signal.SIGUSR1, self.restart_signal_handler)
        # [TODO] Investigate relation between the agent state and the job state
        self.set_agent_state("waiting")
        self._post_initial_agent_data()

    def _post_initial_agent_data(self):
        """Post the initial agent data to the server once on agent startup"""

        self.client.post_advertised_queues()
        self.client.post_advertised_images()

        identifier = self.client.config.get("identifier")
        location = self.client.config.get("location", "")
        provision_type = self.client.config.get("provision_type", "")
        queues = self.client.config.get("job_queues", [])

        agent_data = {
            "location": location,
            "queues": queues,
            "provision_type": provision_type,
        }
        if identifier:
            agent_data["identifier"] = identifier

        self.client.post_agent_data(agent_data)

    def set_agent_state(self, state):
        """Send the agent state to the server"""
        self.client.post_agent_data({"state": state})
        self.client.post_influx(state)

    def get_offline_files(self):
        # Return possible restart filenames with and without dashes
        # i.e. support both:
        #     TESTFLINGER-DEVICE-OFFLINE-devname-001
        #     TESTFLINGER-DEVICE-OFFLINE-devname001
        agent = self.client.config.get("agent_id")
        files = [
            "/tmp/TESTFLINGER-DEVICE-OFFLINE-{}".format(agent),
            "/tmp/TESTFLINGER-DEVICE-OFFLINE-{}".format(
                agent.replace("-", "")
            ),
        ]
        return files

    def get_restart_files(self):
        # Return possible restart filenames with and without dashes
        # i.e. support both:
        #     TESTFLINGER-DEVICE-RESTART-devname-001
        #     TESTFLINGER-DEVICE-RESTART-devname001
        agent = self.client.config.get("agent_id")
        files = [
            "/tmp/TESTFLINGER-DEVICE-RESTART-{}".format(agent),
            "/tmp/TESTFLINGER-DEVICE-RESTART-{}".format(
                agent.replace("-", "")
            ),
        ]
        return files

    def check_offline(self):
        possible_files = self.get_offline_files()
        for offline_file in possible_files:
            if os.path.exists(offline_file):
                self.set_agent_state("offline")
                return offline_file
        self.set_agent_state("waiting")
        return ""

    def check_restart(self):
        possible_files = self.get_restart_files()
        for restart_file in possible_files:
            if os.path.exists(restart_file):
                try:
                    os.unlink(restart_file)
                    logger.info("Restarting agent")
                    self.set_agent_state("offline")
                    sys.exit("Restart Requested")
                except OSError:
                    logger.error(
                        "Restart requested, but unable to remove marker file!"
                    )
                    break

    def mark_device_offline(self):
        # Create the offline file, this should work even if it exists
        open(self.get_offline_files()[0], "w").close()

    def process_jobs(self):
        """Coordinate checking for new jobs and handling them if they exists"""

        TEST_PHASES = [
            TestPhase.UNPACK,
            TestPhase.SETUP,
            TestPhase.PROVISION,
            TestPhase.FIRMWARE_UPDATE,
            TestPhase.TEST,
            TestPhase.ALLOCATE,
            TestPhase.RESERVE,
        ]

        # First, see if we have any old results that we couldn't send last time
        self.retry_old_results()

        self.check_restart()
        job_data = self.client.check_jobs()
        while job_data:
            try:
                job_id = job_data.get("job_id")

                # create emitter and broadcast job start
                event_emitter = EventEmitter(
                    job_data.get("job_queue"),
                    job_data.get("job_status_webhook"),
                    self.client,
                    job_id,
                )
                job_end_reason = TestEvent.NORMAL_EXIT

                logger.info("Starting job %s", job_id)
                event_emitter.emit_event(
                    TestEvent.JOB_START,
                    f"{self.client.server}/jobs/{job_id}",
                )
                self.client.post_agent_data({"job_id": job_id})

                # specify directories and result files
                rundir = os.path.join(
                    self.client.config.get("execution_basedir"), job_id
                )
                os.makedirs(rundir)
                error_log_path = os.path.join(
                    rundir, "device-connector-error.json"
                )
                # Clear error log before starting
                open(error_log_path, "w").close()

                # Dump the job data to testflinger.json in our execution dir
                with open(os.path.join(rundir, "testflinger.json"), "w") as f:
                    json.dump(job_data, f)
                # Create json outcome file where phases will store their output
                with open(
                    os.path.join(rundir, "testflinger-outcome.json"), "w"
                ) as f:
                    json.dump({}, f)

                # create the job and go through its phases
                job = TestflingerJob(job_data, self.client, rundir)
                for phase in TEST_PHASES:
                    # First make sure the job hasn't been cancelled
                    if (
                        self.client.check_job_state(job_id)
                        == JobState.CANCELLED
                    ):
                        logger.info("Job cancellation was requested, exiting.")
                        event_emitter.emit_event(TestEvent.CANCELLED)
                        break

                    self.client.post_job_state(job_id, phase)
                    self.set_agent_state(phase)
                    event_emitter.emit_event(TestEvent(phase + "_start"))
                    exit_code, exit_event, exit_reason = job.run_test_phase(
                        phase
                    )
                    self.client.post_influx(phase, exit_code)
                    event_emitter.emit_event(exit_event, exit_reason)
                    detail = ""
                    if exit_code:
                        # exit code 46 is our indication that recovery failed!
                        # In this case, we need to mark the device offline
                        if exit_code == 46:
                            self.mark_device_offline()
                            exit_event = TestEvent.RECOVERY_FAIL
                        else:
                            exit_event = TestEvent(phase + "_fail")
                        detail = parse_error_logs(error_log_path, phase)
                    else:
                        exit_event = TestEvent(phase + "_success")
                    event_emitter.emit_event(exit_event, detail)
                    if phase == TestPhase.PROVISION:
                        self.client.post_provision_log(
                            job_id, exit_code, exit_event
                        )
                    if exit_code and phase != TestPhase.TEST:
                        logger.debug("Phase %s failed, aborting job" % phase)
                        job_end_reason = exit_event
                        break
            except Exception as e:
                logger.exception(e)
            finally:
                # Always run the cleanup, even if the job was cancelled
                event_emitter.emit_event(TestEvent.CLEANUP_START)
                job.run_test_phase(TestPhase.CLEANUP)
                event_emitter.emit_event(TestEvent.CLEANUP_SUCCESS)
                event_emitter.emit_event(TestEvent.JOB_END, job_end_reason)
                # clear job id
                self.client.post_agent_data({"job_id": ""})

            try:
                self.client.transmit_job_outcome(rundir)
            except Exception as e:
                # TFServerError will happen if we get other-than-good status
                # Other errors can happen too for things like connection
                # problems
                logger.exception(e)
                results_basedir = self.client.config.get("results_basedir")
                shutil.move(rundir, results_basedir)
            self.set_agent_state(JobState.WAITING)

            self.check_restart()
            if self.check_offline():
                # Don't get a new job if we are now marked offline
                break
            job_data = self.client.check_jobs()

    def retry_old_results(self):
        """Retry sending results that we previously failed to send"""

        results_dir = self.client.config.get("results_basedir")
        # List all the directories in 'results_basedir', where we store the
        # results that we couldn't transmit before
        old_results = [
            os.path.join(results_dir, d)
            for d in os.listdir(results_dir)
            if os.path.isdir(os.path.join(results_dir, d))
        ]
        for result in old_results:
            try:
                logger.info("Attempting to send result: %s" % result)
                self.client.transmit_job_outcome(result)
            except TFServerError:
                # Problems still, better luck next time?
                pass

    def restart_signal_handler(self, _, __):
        """
        If we receive the restart signal, tell the agent to restart safely when
        it is not running a job
        """
        logger.info("Marked agent for restart")
        restart_file = self.get_restart_files()[0]
        open(restart_file, "w").close()
