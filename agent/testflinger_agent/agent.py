# Copyright (C) 2017-2020 Canonical
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
from pathlib import Path
import shutil
import tarfile
import tempfile

from testflinger_agent.job import TestflingerJob
from testflinger_agent.errors import TFServerError
from testflinger_agent.config import ATTACHMENTS_DIR

logger = logging.getLogger(__name__)


def secure_filter(member, path):
    """Combine the `data` filter with custom attachment filtering

    Makes sure that the starting folder for all attachments coincides
    with one of the supported phases, i.e. that the attachment archive
    has been created properly and no attachment will be extracted to an
    unexpected location.
    """
    if not member.name.startswith(("provision", "firmware_update", "test")):
        raise tarfile.OutsideDestinationError(member, path)
    return tarfile.data_filter(member, path)


class TestflingerAgent:
    def __init__(self, client):
        self.client = client
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
                    raise SystemExit("Restart Requested")
                except OSError:
                    logger.error(
                        "Restart requested, but unable to remove marker file!"
                    )
                    break

    def mark_device_offline(self):
        # Create the offline file, this should work even if it exists
        open(self.get_offline_files()[0], "w").close()

    def unpack_attachments(self, job_data: dict, cwd: Path):
        """Download and unpack the attachments associated with a job"""
        job_id = job_data["job_id"]

        with tempfile.NamedTemporaryFile(suffix="tar.gz") as archive_tmp:
            archive_path = Path(archive_tmp.name)
            # download attachment archive
            self.client.get_attachments(job_id, path=archive_path)
            # extract archive into the attachments folder
            with tarfile.open(archive_path, "r:gz") as tar:
                tar.extractall(cwd / ATTACHMENTS_DIR, filter=secure_filter)

    def process_jobs(self):
        """Coordinate checking for new jobs and handling them if they exists"""
        TEST_PHASES = [
            "setup",
            "provision",
            "firmware_update",
            "test",
            "allocate",
            "reserve",
        ]

        # First, see if we have any old results that we couldn't send last time
        self.retry_old_results()

        self.check_restart()

        job_data = self.client.check_jobs()
        while job_data:
            try:
                job = TestflingerJob(job_data, self.client)
                logger.info("Starting job %s", job.job_id)
                rundir = os.path.join(
                    self.client.config.get("execution_basedir"), job.job_id
                )
                os.makedirs(rundir)

                self.client.post_agent_data({"job_id": job.job_id})

                # handle job attachments, if any
                if job_data.get("attachments", "none") == "complete":
                    self.unpack_attachments(job_data, cwd=Path(rundir))

                # Dump the job data to testflinger.json in our execution dir
                with open(os.path.join(rundir, "testflinger.json"), "w") as f:
                    json.dump(job_data, f)
                # Create json outcome file where phases will store their output
                with open(
                    os.path.join(rundir, "testflinger-outcome.json"), "w"
                ) as f:
                    json.dump({}, f)

                for phase in TEST_PHASES:
                    # First make sure the job hasn't been cancelled
                    if self.client.check_job_state(job.job_id) == "cancelled":
                        logger.info("Job cancellation was requested, exiting.")
                        break
                    self.client.post_job_state(job.job_id, phase)
                    self.set_agent_state(phase)
                    exitcode = job.run_test_phase(phase, rundir)

                    self.client.post_influx(phase, exitcode)

                    # exit code 46 is our indication that recovery failed!
                    # In this case, we need to mark the device offline
                    if exitcode == 46:
                        self.mark_device_offline()
                    if phase != "test" and exitcode:
                        logger.debug("Phase %s failed, aborting job" % phase)
                        break
            except Exception as e:
                logger.exception(e)
            finally:
                # Always run the cleanup, even if the job was cancelled
                job.run_test_phase("cleanup", rundir)
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
            self.set_agent_state("waiting")

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
