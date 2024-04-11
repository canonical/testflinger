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

logger = logging.getLogger(__name__)


def tmp_dir() -> Path:
    """Create a temporary directory and return the path to it"""
    return Path(tempfile.mkdtemp())


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

        # download attachment archive to a unique temporary folder
        archive_dir = tmp_dir()
        archive_path = self.client.get_attachments(
            job_id=job_data["job_id"], path=archive_dir
        )
        if archive_path is None:
            raise FileNotFoundError
        # extract archive data to a unique temporary folder and clean up
        extracted_dir = tmp_dir()
        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(extracted_dir, filter="data")
        shutil.rmtree(archive_dir)

        # [TODO] clarify if this is an appropriate destination for extraction
        attachment_dir = cwd / "attachments"

        # move/rename extracted archive files to their specified destinations
        for phase in ("provision", "firmware_update", "test"):
            try:
                attachments = job_data[f"{phase}_data"]["attachments"]
            except KeyError:
                continue
            for attachment in attachments:
                original = Path(attachment["local"])
                if original.is_absolute():
                    # absolute filenames become relative
                    original = original.relative_to(original.root)
                # use renaming destination, if provided
                # otherwise use the original one
                destination_path = (
                    attachment_dir / phase / attachment.get("agent", original)
                )
                # create intermediate path to destination, if required
                destination_path.resolve().parent.mkdir(
                    parents=True, exist_ok=True
                )
                # move file
                source_path = extracted_dir / phase / original
                shutil.move(source_path, destination_path)

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
