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

import logging
import os
import shutil
import signal
import sys

from testflinger_agent.job import TestflingerJob
from testflinger_agent.errors import TFServerError
from testflinger_common.enums import JobState, TestPhase, TestEvent


logger = logging.getLogger(__name__)


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

        # First, see if we have any old results that we couldn't send last time
        self.retry_old_results()

        self.check_restart()
        job_data = self.client.check_jobs()
        while job_data:
            job_id = job_data["job_id"]
            try:
                # Create the job
                job = TestflingerJob(job_data, self.client)

                # Let the server know the agent has picked up the job
                self.client.post_agent_data({"job_id": job_id})
                job.start()

                if job.check_attachments():
                    job.unpack_attachments()

                # Go through the job phases
                for phase in job.phase_sequence:

                    # First make sure the job hasn't been cancelled
                    if job.check_cancel():
                        job.cancel()
                        break

                    # Run the phase or skip it
                    if job.go(phase):
                        self.set_agent_state(phase)
                        job.run(phase)
                        if job.check_end():
                            break
            except Exception as error:
                logger.exception(f"{type(error).__name__}: {error}")
            finally:
                phase = TestPhase.CLEANUP
                # Always run the cleanup, even if the job was cancelled
                if job.go(phase):
                    self.set_agent_state(phase)
                    job.run(phase)

            # let the server know the agent is available (clear job id)
            job.end()
            self.client.post_agent_data({"job_id": ""})

            provision_result = job.phases[TestPhase.PROVISION].result
            if (
                provision_result is not None
                and provision_result.event == TestEvent.RECOVERY_FAIL
            ):
                self.mark_device_offline()

            try:
                self.client.transmit_job_outcome(str(job.params.rundir))
            except Exception as e:
                # TFServerError will happen if we get other-than-good status
                # Other errors can happen too for things like connection
                # problems
                logger.exception(e)
                results_basedir = self.client.config.get("results_basedir")
                shutil.move(job.params.rundir, results_basedir)
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
