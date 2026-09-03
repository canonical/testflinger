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
import shutil
import signal
import sys
import tempfile
import time
from pathlib import Path

from testflinger_common.enums import (
    AgentMode,
    AgentState,
    JobState,
    TestEvent,
    TestPhase,
)

from testflinger_agent.config import ATTACHMENTS_DIR
from testflinger_agent.errors import TFServerError
from testflinger_agent.event_emitter import EventEmitter
from testflinger_agent.handlers import (
    AgentHeartbeatHandler,
    AgentStatusHandler,
)
from testflinger_agent.job import TestflingerJob
from testflinger_agent.metrics import PrometheusHandler
from testflinger_agent.os_release import query_dut_release

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
    """Combine the `data` filter with custom attachment filtering.

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


def parse_error_logs(error_log_path: Path, phase: str):
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
    __test__ = False
    """This prevents pytest from trying to run this class as a test."""

    def __init__(self, client):
        self.client = client
        self.agent_id = self.client.config.get("agent_id")
        self.status_handler = AgentStatusHandler()
        self.heartbeat_handler = AgentHeartbeatHandler(
            self.client, heartbeat_frequency=1
        )
        signal.signal(signal.SIGUSR1, self.restart_signal_handler)
        self.set_agent_mode(AgentMode.ONLINE)
        self.set_agent_state(AgentState.WAITING)
        self._post_initial_agent_data()
        self.metrics_handler = PrometheusHandler(
            self.client.config.get("metrics_endpoint_port"), self.agent_id
        )

    def _post_initial_agent_data(self):
        """Post the initial agent data to the server once on agent startup."""
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

    def set_agent_mode(self, mode: AgentMode, comment: str = "") -> None:
        """Send the agent operating mode to the server.

        :param mode: AgentMode to report.
        :param comment: Reason for the mode change. Required for OFFLINE
                        and MAINTENANCE; ignored for ONLINE and RESTART.
        """
        data: dict = {"mode": mode}
        if comment:
            data["comment"] = comment
        self.client.post_agent_data(data)

    def set_agent_state(self, state: AgentState) -> None:
        """Send the agent sub-state to the server.

        Only valid for ONLINE and MAINTENANCE modes.  OFFLINE and RESTART
        carry no sub-state and should not call this method.

        :param state: AgentState sub-state to report.
        """
        self.client.post_agent_data({"state": state})

    def get_agent_mode(self) -> tuple:
        """Get the agent mode from the server.

        :return: (AgentMode, comment) tuple. Returns (AgentMode.ONLINE, "")
                 if the mode cannot be retrieved, so the agent continues
                 operating normally rather than silently halting.
        """
        agent_data = self.client.get_agent_data(self.agent_id)

        self.heartbeat_handler.update(agent_data)

        comment = agent_data.get("comment", "")
        mode_value = agent_data.get("mode")
        if mode_value is None:
            logger.error(
                "Unable to retrieve mode for agent: %s", self.agent_id
            )
            return (AgentMode.ONLINE, comment)
        try:
            return (AgentMode(mode_value), comment)
        except ValueError:
            logger.error(
                "Unknown mode value '%s' for agent: %s",
                mode_value,
                self.agent_id,
            )
            return (AgentMode.ONLINE, comment)

    def check_mode_change(self) -> tuple:
        """Check with the server what operating mode we should be in.

        :return: (AgentMode, comment). Returns AgentMode.ONLINE if no
                 mode change is needed.
        """
        mode, comment = self.get_agent_mode()

        if mode in (AgentMode.OFFLINE, AgentMode.MAINTENANCE):
            return (mode, comment)
        # Device fault flagged locally — treat as maintenance.
        if self.status_handler.needs_offline:
            return (AgentMode.MAINTENANCE, self.status_handler.comment)
        return (AgentMode.ONLINE, comment)

    def check_restart(self) -> tuple:
        """Determine if the agent requires a restart.

        :return: (needs_restart: bool, comment: str).
        """
        mode, comment = self.get_agent_mode()

        if mode == AgentMode.RESTART:
            return (True, comment)
        if self.status_handler.needs_restart and mode != AgentMode.OFFLINE:
            return (True, self.status_handler.comment)
        return (False, comment)

    def restart_agent(self, comment: str = "") -> None:
        """Perform the restart action when not busy."""
        logger.info("Restarting agent")
        self.set_agent_mode(AgentMode.OFFLINE, comment)
        sys.exit("Restart Requested")

    def enter_maintenance_mode(self, comment: str = "") -> None:
        """Enter maintenance mode: restrict queues to the maintenance queue."""
        maintenance_queue = f"{self.agent_id}_maintenance"
        logger.info(
            "Entering maintenance mode – advertising queue: %s",
            maintenance_queue,
        )
        self.set_agent_mode(AgentMode.MAINTENANCE, comment)
        self.set_agent_state(AgentState.WAITING)
        self.client.post_agent_data({"queues": [maintenance_queue]})
        self.status_handler.update(offline=False, comment=comment)

    def exit_maintenance_mode(self) -> None:
        """Exit maintenance mode: restore the normal job queues."""
        logger.info("Exiting maintenance mode – restoring normal queues")
        queues = self.client.config.get("job_queues", [])
        self.client.post_agent_data({"queues": queues})
        self.set_agent_mode(AgentMode.ONLINE)
        self.set_agent_state(AgentState.WAITING)

    def go_offline(self, comment: str = "") -> None:
        """Go offline: advertise no queues and set OFFLINE mode."""
        logger.info("Going offline – advertising no queues")
        self.set_agent_mode(AgentMode.OFFLINE, comment)
        self.client.post_agent_data({"queues": []})

    def exit_offline(self) -> None:
        """Exit offline: restore normal queues and return to online."""
        logger.info("Exiting offline – restoring normal queues")
        queues = self.client.config.get("job_queues", [])
        self.client.post_agent_data({"queues": queues})
        self.set_agent_mode(AgentMode.ONLINE)
        self.set_agent_state(AgentState.WAITING)

    def unpack_attachments(self, job_data: dict, cwd: Path):
        """Download and unpack the attachments associated with a job."""
        job_id = job_data["job_id"]

        with tempfile.NamedTemporaryFile(suffix="tar.gz") as archive_tmp:
            archive_path = Path(archive_tmp.name)
            # download attachment archive
            logger.info("Downloading attachments for %s", job_id)
            self.client.get_attachments(job_id, path=archive_path)
            # extract archive into the attachments folder
            logger.info("Unpacking attachments for %s", job_id)
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

    def get_job_data(self):
        return self.client.check_jobs()

    def process_jobs(self):
        """Coordinate checks for new jobs and handling them if they exists."""
        test_phases = [
            TestPhase.SETUP,
            TestPhase.PROVISION,
            TestPhase.FIRMWARE_UPDATE,
            TestPhase.TEST,
            TestPhase.ALLOCATE,
            TestPhase.RESERVE,
        ]

        # First, see if we have any old results that we couldn't send last time
        self.retry_old_results()

        # Before picking up jobs, check what mode we should be in.
        mode, mode_comment = self.check_mode_change()
        needs_restart, restart_comment = self.check_restart()

        # Update status handler — mode change takes priority over restart
        if mode != AgentMode.ONLINE:
            self.status_handler.update(offline=True, comment=mode_comment)
        elif needs_restart:
            self.status_handler.update(
                restart=needs_restart,
                offline=self.status_handler.needs_offline,
                comment=restart_comment,
            )

        # Act on mode or restart
        if self.status_handler.needs_offline:
            if mode == AgentMode.OFFLINE:
                self.go_offline(self.status_handler.comment)
            else:
                self.enter_maintenance_mode(self.status_handler.comment)
            return
        if self.status_handler.needs_restart:
            self.restart_agent(self.status_handler.comment)

        # Check for the first job before looping for more
        job_data = self.get_job_data()
        while job_data:
            rundir = None
            job = None
            event_emitter = None
            release = ""
            identifier = self.client.config.get("identifier", "")
            job_end_reason = TestEvent.NORMAL_EXIT
            try:
                job = TestflingerJob(job_data, self.client)
                event_emitter = EventEmitter(
                    job_data.get("job_queue"),
                    job_data.get("job_status_webhook"),
                    self.client,
                    job.job_id,
                )

                logger.info("Starting job %s", job.job_id)
                self.metrics_handler.report_new_job()
                event_emitter.emit_event(
                    TestEvent.JOB_START,
                    f"{self.client.server}/jobs/{job.job_id}",
                )
                rundir = (
                    Path(self.client.config.get("execution_basedir"))
                    / job.job_id
                )
                rundir.mkdir(parents=True, exist_ok=False)

                # Dump the job data to testflinger.json in our execution dir
                with (rundir / "testflinger.json").open("w") as f:
                    json.dump(job_data, f)
                # Create json outcome file where phases will store their output
                with (rundir / "testflinger-outcome.json").open("w") as f:
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
                    self.unpack_attachments(job_data, cwd=rundir)

                error_log_path = rundir / "device-connector-error.json"
                # Clear  error log before starting
                open(error_log_path, "w").close()

                for phase in test_phases:
                    # First make sure the job hasn't been cancelled
                    if (
                        self.client.check_job_state(job.job_id)
                        == JobState.CANCELLED
                    ):
                        logger.info("Job cancellation was requested, exiting.")
                        event_emitter.emit_event(TestEvent.CANCELLED)
                        break

                    # Before posting status, check if action is needed
                    if not self.status_handler.needs_offline:
                        mode, mode_comment = self.check_mode_change()
                        if mode != AgentMode.ONLINE:
                            self.status_handler.update(
                                offline=True, comment=mode_comment
                            )

                    if not self.status_handler.needs_restart:
                        needs_restart, restart_comment = self.check_restart()
                        if needs_restart:
                            self.status_handler.update(
                                restart=needs_restart,
                                offline=self.status_handler.needs_offline,
                                comment=restart_comment,
                            )

                    self.client.post_job_state(job.job_id, phase)
                    self.set_agent_state(phase)
                    event_emitter.emit_event(TestEvent(f"{phase}_start"))
                    # Register start time to measure phase duration
                    phase_start = time.time()
                    exit_code, exit_event, exit_reason = job.run_test_phase(
                        phase, rundir
                    )
                    phase_end = time.time()

                    # Query DUT release after successful provision
                    if phase == TestPhase.PROVISION and not exit_code:
                        device_info = job.get_device_info(rundir)
                        if device_info and (
                            device_ip := device_info.get(
                                "device_info", {}
                            ).get("device_ip")
                        ):
                            username = (job_data.get("test_data") or {}).get(
                                "test_username", "ubuntu"
                            )
                            release = query_dut_release(device_ip, username)

                    # Report phase duration to metrics handler
                    self.metrics_handler.report_phase_duration(
                        phase,
                        int(phase_end - phase_start),
                        identifier=identifier,
                        release=release,
                    )
                    event_emitter.emit_event(exit_event, exit_reason)
                    detail = ""
                    if exit_code:
                        # exit code 46 is our indication that recovery failed!
                        # In this case, we need to mark the device offline
                        if exit_code == 46:
                            comment = (
                                "Set to offline by agent. Recovery failed"
                                f" during job '{job.job_id}' execution."
                            )
                            self.enter_maintenance_mode(comment)
                            exit_event = TestEvent.RECOVERY_FAIL
                            # Report recovery failure in a dedicated metric
                            self.metrics_handler.report_recovery_failures()
                        else:
                            exit_event = TestEvent(f"{phase}_fail")
                        detail = parse_error_logs(error_log_path, phase)
                        self.metrics_handler.report_job_failure(phase)
                    else:
                        exit_event = TestEvent(f"{phase}_success")
                    event_emitter.emit_event(exit_event, detail)
                    if phase == TestPhase.PROVISION:
                        self.client.post_provision_log(
                            job.job_id, exit_code, exit_event
                        )
                    if exit_code and phase != TestPhase.TEST:
                        logger.debug("Phase %s failed, aborting job", phase)
                        job_end_reason = exit_event
                        break
            except Exception as e:
                logger.exception(e)
            finally:
                # Always run the cleanup, even if the job was cancelled
                if event_emitter:
                    event_emitter.emit_event(TestEvent.CLEANUP_START)
                    if job and rundir:
                        exit_code, _, _ = job.run_test_phase(
                            TestPhase.CLEANUP, rundir
                        )
                        if exit_code:
                            logger.debug("Issue with cleanup phase")
                            event_emitter.emit_event(TestEvent.CLEANUP_FAIL)
                        else:
                            event_emitter.emit_event(TestEvent.CLEANUP_SUCCESS)
                    event_emitter.emit_event(TestEvent.JOB_END, job_end_reason)

            if rundir:
                try:
                    self.client.transmit_job_outcome(rundir)
                except Exception as e:
                    # TFServerError will happen if we get other-than-good
                    # status; other errors can happen too for things like
                    # connection problems
                    logger.exception(e)
                    results_basedir = Path(
                        self.client.config.get("results_basedir")
                    )
                    shutil.move(rundir, results_basedir)

            # Complete cleanup only if server is reachable
            self.client.wait_for_server_connectivity()

            # Check if a mode change is needed after job completion
            mode, mode_comment = self.check_mode_change()
            if mode != AgentMode.ONLINE:
                if mode == AgentMode.OFFLINE:
                    self.go_offline(mode_comment)
                else:
                    self.enter_maintenance_mode(mode_comment)
                # Don't get a new job if we are now in a non-online mode
                break
            # Check if restart is needed after job completion
            if self.status_handler.needs_restart:
                self.restart_agent(self.status_handler.comment)

            # If no restart or mode change needed, set agent to wait for
            # new job
            self.set_agent_state(AgentState.WAITING)
            job_data = self.get_job_data()

    def retry_old_results(self):
        """Retry sending results that we previously failed to send."""
        results_dir = Path(self.client.config.get("results_basedir"))
        # List all the directories in 'results_basedir', where we store the
        # results that we couldn't transmit before
        old_results = [
            entry for entry in results_dir.iterdir() if entry.is_dir()
        ]
        for result in old_results:
            try:
                logger.info("Attempting to send result: %s", result)
                self.client.transmit_job_outcome(result)
            except TFServerError:
                # Problems still, better luck next time?
                pass

    def restart_signal_handler(self, _, __):
        """
        If we receive the restart signal, tell the agent to restart safely when
        it is not running a job.
        """
        logger.info("Marked agent for restart")
        # If there is a pending offline, preserve the offline flag
        self.status_handler.update(
            restart=True,
            offline=self.status_handler.needs_offline,
            comment="Restart signal detected from supervisor process",
        )
