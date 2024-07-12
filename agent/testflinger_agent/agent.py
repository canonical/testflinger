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
import tempfile

from testflinger_agent.job import TestflingerJob
from testflinger_agent.errors import TFServerError
from testflinger_agent.config import ATTACHMENTS_DIR
from testflinger_agent.event_emitter import EventEmitter
from testflinger_common.enums import JobState, TestPhase, TestEvent


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


def secure_filter(member, path):
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
        ("provision/", "firmware_update/", "test/")
    ):
        # trying to extract in an invalid folder, under the attachments folder
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
            logger.info(f"Downloading attachments for {job_id}")
            self.client.get_attachments(job_id, path=archive_path)
            # extract archive into the attachments folder
            logger.info(f"Unpacking attachments for {job_id}")
            with tarfile.open(archive_path, "r:gz") as tar:
                tar.extractall(cwd / ATTACHMENTS_DIR, filter=secure_filter)

        # side effect: remove all attachment data from `job_data`
        # (so there is no interference with existing processes, especially
        # provisioning or firmware update, which are triggered when these
        # sections are not empty)
        for phase in (
            TestPhase.PROVISION,
            TestPhase.FIRMWARE_UPDATE,
            TestPhase.TEST,
        ):
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

    def process_jobs(self):
        """Coordinate checking for new jobs and handling them if they exists"""

        TEST_PHASES = [
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
                job = TestflingerJob(job_data, self.client)
                event_emitter = EventEmitter(
                    job_data.get("job_queue"),
                    job_data.get("job_status_webhook"),
                    self.client,
                    job.job_id,
                )
                job_end_reason = TestEvent.NORMAL_EXIT

                logger.info("Starting job %s", job.job_id)
                event_emitter.emit_event(
                    TestEvent.JOB_START,
                    f"{self.client.server}/job/{job.job_id}/events",
                )
                rundir = os.path.join(
                    self.client.config.get("execution_basedir"), job.job_id
                )
                os.makedirs(rundir)

                self.client.post_agent_data({"job_id": job.job_id})

                # Dump the job data to testflinger.json in our execution dir
                with open(os.path.join(rundir, "testflinger.json"), "w") as f:
                    json.dump(job_data, f)
                # Create json outcome file where phases will store their output
                with open(
                    os.path.join(rundir, "testflinger-outcome.json"), "w"
                ) as f:
                    json.dump({}, f)

                # Handle job attachments, if any.
                #
                # *Always* place this after creating "testflinger.json":
                # - If there is an unpacking error, the file is required
                #   for reporting
                # - The `unpack_attachments` method has a side effect on
                #   `job_data`: it removes attachment data. However, the
                #   file will still contain all the data received and
                #   pass it on to the device container
                if job_data.get("attachments_status") == "complete":
                    self.unpack_attachments(job_data, cwd=Path(rundir))

                for phase in TEST_PHASES:
                    # First make sure the job hasn't been cancelled
                    if (
                        self.client.check_job_state(job.job_id)
                        == JobState.CANCELLED
                    ):
                        logger.info("Job cancellation was requested, exiting.")
                        event_emitter.emit_event(TestEvent.CANCELLED)
                        break

                    self.client.post_job_state(job.job_id, phase)
                    self.set_agent_state(phase)

                    event_emitter.emit_event(TestEvent(phase + "_start"))
                    exit_code, exit_event, exit_reason = job.run_test_phase(
                        phase, rundir
                    )
                    self.client.post_influx(phase, exit_code)
                    event_emitter.emit_event(exit_event, exit_reason)

                    if exit_code:
                        # exit code 46 is our indication that recovery failed!
                        # In this case, we need to mark the device offline
                        if exit_code == 46:
                            self.mark_device_offline()
                            exit_event = TestEvent.RECOVERY_FAIL
                        else:
                            exit_event = TestEvent(phase + "_fail")
                        event_emitter.emit_event(exit_event)
                        if phase == "provision":
                            self.client.post_provision_log(
                                job.job_id, exit_code, exit_event
                            )
                        if phase != "test":
                            logger.debug(
                                "Phase %s failed, aborting job" % phase
                            )
                            job_end_reason = exit_event
                            break
                    else:
                        event_emitter.emit_event(TestEvent(phase + "_success"))
            except Exception as e:
                logger.exception(e)
            finally:
                # Always run the cleanup, even if the job was cancelled
                event_emitter.emit_event(TestEvent.CLEANUP_START)
                job.run_test_phase(TestPhase.CLEANUP, rundir)
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
