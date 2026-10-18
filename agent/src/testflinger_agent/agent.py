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
from testflinger_agent.handlers import AgentHeartbeatHandler
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
        self.current_mode = None  # Set in _set_startup_mode
        self.commanded_mode = None
        self.needs_restart = False
        self.comment = ""
        self.updated_at = None
        self.restricted_to = {}
        self.heartbeat_handler = AgentHeartbeatHandler(
            self.client, heartbeat_frequency=1
        )
        signal.signal(signal.SIGUSR1, self.restart_signal_handler)
        self._post_initial_agent_data()
        self._set_startup_mode()
        self.metrics_handler = PrometheusHandler(
            self.client.config.get("metrics_endpoint_port"), self.agent_id
        )

    def _set_startup_mode(self) -> None:
        """Set the agent mode on startup, preserving server-side state.

        Restarting an agent must not silently end an active maintenance
        period, nor bring an offline agent back online:

        - If we were in MAINTENANCE, ONLINE or OFFLINE before the restart, be
          sure to come back up in that same state.
        - If server commands RESTART at startup, honor it immediately.
          Note: Because the server will preserve the last known mode as the
          next commanded_mode when it receives the agent's mode of RESTART,
          the commanded_mode won't be RESTART unless it has been commanded
          by the server and not acknowledged by the agent. Therefore, we must
          oblige and restart again now.
        """
        self.update_agent_data()

        if self.commanded_mode == AgentMode.RESTART:
            logger.info("Server commanding agent restart on startup.")
            self.restart_agent(self.comment)
            return

        if self.commanded_mode == AgentMode.MAINTENANCE:
            logger.info("Agent resuming maintenance mode on startup.")
            self.enter_maintenance_mode(self.comment)
            return

        if self.commanded_mode == AgentMode.OFFLINE:
            logger.info("Agent resuming offline operation.")
            self.go_offline(self.comment)
            return

        self.set_agent_mode(AgentMode.ONLINE, state=AgentState.WAITING)

    def _post_initial_agent_data(self):
        """Post the initial agent data to the server once on agent startup."""
        self.client.post_advertised_queues()
        self.client.post_advertised_images()

        identifier = self.client.config.get("identifier")
        location = self.client.config.get("location", "")
        provision_type = self.client.config.get("provision_type", "")
        queues = self.client.config.get("job_queues", [])
        links = self.client.config.get("links", [])

        agent_data = {
            "location": location,
            "queues": queues,
            "provision_type": provision_type,
        }
        if identifier:
            agent_data["identifier"] = identifier

        if links:
            agent_data["links"] = links

        self.client.post_agent_data(agent_data)

    def set_agent_mode(
        self,
        mode: AgentMode,
        comment: str = "",
        state: AgentState | None = None,
        queues: list[str] | None = None,
    ) -> None:
        """Update the local agent operating mode and send it to the server.

        :param mode: AgentMode to report.
        :param comment: Optional reason for the mode change. An empty value
            clears the server-side comment.
        :param state: Only relevant for ONLINE and MAINTENANCE modes, default
            is None (no change).
        :param queues: If set, update the qgent queues to match this list.
        """
        self.current_mode = mode
        self.comment = comment
        data = {"mode": self.current_mode, "comment": comment}
        if state and self.current_mode in (
            AgentMode.ONLINE,
            AgentMode.MAINTENANCE,
        ):
            data.update({"state": state})
        if queues is not None:
            data.update({"queues": queues})
        self.client.post_agent_data(data)

    def send_agent_state(self, state: AgentState) -> None:
        """Send the agent sub-state to the server.

        Only valid for ONLINE and MAINTENANCE modes.  OFFLINE and RESTART
        carry no sub-state and should not call this method.

        :param state: AgentState sub-state to report.
        """
        self.client.post_agent_data({"state": state})

    def update_agent_data(self):
        """Get the agent data from the server and update the agent's data.

        Resolve the agent's mode according to priority:
        1. commanded_mode from server (admin command)
        2. current_mode (what agent is currently in)
        3. ONLINE (safe default if nothing is known)

        Note: We do NOT use 'mode' field for decisions. The 'mode' field is
        purely informational (agent's last reported state). The agent only
        changes mode when server issues explicit 'commanded_mode'.
        """
        agent_data = self.client.get_agent_data(self.agent_id)
        self.updated_at = agent_data.get("updated_at")
        self.restricted_to = agent_data.get("restricted_to", {})

        # Priority 1: commanded_mode from server (admin command)
        commanded_mode = agent_data.get("commanded_mode")
        if commanded_mode:
            try:
                self.commanded_mode = AgentMode(commanded_mode)
                self.comment = agent_data.get("comment", "")
                return
            except ValueError:
                logger.error("Unknown mode value '%s'.", commanded_mode)
                # Fall through to priority 2

        # Priority 2: current_mode (what agent is currently in)
        if self.current_mode is not None:
            self.commanded_mode = self.current_mode
            return

        # Priority 3: safe default
        logger.info("No mode information available; defaulting to ONLINE.")
        self.commanded_mode = AgentMode.ONLINE

    def determine_next_mode(self) -> tuple[AgentMode, str]:
        """Check with the server what operating mode we should be in.

        Resolve internal mode versus the server's commanded_mode to determine
        what the next mode should be.

        :return: (AgentMode, comment) tuple.
        """
        # If the supervisor process has commanded us to restart, we must do
        # that instead of taking our direction from the server.
        if self.needs_restart:
            return (AgentMode.RESTART, self.comment)

        # Get the latest commanded_mode from the server:
        self.update_agent_data()
        return (self.commanded_mode, self.comment)

    def handle_mode_changes(self) -> bool:
        """Respond to requested mode changes."""
        # determine_next_mode will resolve the agent's internal state against
        # that of the server and determine what the next mode will be.
        next_mode, comment = self.determine_next_mode()

        # Now, we need to simply as to change into that mode if not already
        # in the correct mode:
        if self.current_mode != next_mode:
            if next_mode == AgentMode.RESTART:
                self.restart_agent(comment)
            elif next_mode == AgentMode.OFFLINE:
                self.go_offline(comment)
            elif next_mode == AgentMode.MAINTENANCE:
                self.enter_maintenance_mode(comment)
            else:
                self.go_online()

        if next_mode in (AgentMode.ONLINE, AgentMode.MAINTENANCE):
            return True
        else:
            return False

    def restart_agent(self, comment: str = "") -> None:
        """Request restart mode, then exit so the supervisor restarts us."""
        logger.info("Restarting agent")
        # Must let the server know we're restarting so that it can determine
        # our next startup mode.
        self.set_agent_mode(AgentMode.RESTART, comment)
        sys.exit("Restart Requested")

    def enter_maintenance_mode(self, comment: str = "") -> None:
        """Enter maintenance mode: restrict queues to the maintenance queue."""
        logger.info(
            "Entering maintenance mode – advertising queue: %s",
            self.client.maintenance_queue,
        )
        self.set_agent_mode(
            AgentMode.MAINTENANCE,
            comment,
            state=AgentState.WAITING,
            queues=[self.client.maintenance_queue],
        )

    def go_offline(self, comment: str = "") -> None:
        """Go offline: advertise no queues and set OFFLINE mode."""
        logger.info("Going offline – monitoring maintenance queue")
        self.set_agent_mode(AgentMode.OFFLINE, comment, queues=[])

    def go_online(self) -> None:
        """Go online: restore normal queues and return to online."""
        logger.info("Returning online – restoring normal queues")
        queues = self.client.config.get("job_queues", [])
        self.set_agent_mode(
            AgentMode.ONLINE, state=AgentState.WAITING, queues=queues
        )

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

    def get_a_job(self):
        return self.client.check_jobs(self.restricted_to, self.current_mode)

    def process_one_job(self):
        """Coordinate checks for new jobs and handling them if they exist."""
        job_data = self.get_a_job()
        if not job_data:
            return

        # Reset variables at the top of the job loop.
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

            # Create the directory which the job will be run from:
            rundir = (
                Path(self.client.config.get("execution_basedir")) / job.job_id
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

            # Clear device-connector error log before starting
            error_log_path = rundir / "device-connector-error.json"
            open(error_log_path, "w").close()

            # Now that we are ready to run the job, we will progress
            # sequentially through each defined job phase, saving cleanup
            # until the end and handling it specially.
            for phase in (p for p in TestPhase if p != TestPhase.CLEANUP):
                # At the start of each phase we will confirm that the job
                # is still relevant and hasn't been canceled, if the job
                # is canceled we will break out of the loop and do cleanup.
                if (
                    self.client.check_job_state(job.job_id)
                    == JobState.CANCELLED
                ):
                    logger.info("Job cancellation was requested, exiting.")
                    event_emitter.emit_event(TestEvent.CANCELLED)
                    break

                # TODO:
                #  Identify and schedule deferred mode changes; no longer
                #  need to be here since the server will support a
                #  commanded_mode to clearly indicate the intended next
                #  mode once this job is complete.
                #  After processing this job, we will then once again act
                #  upon the commanded mode (in the outer loop)

                # TODO: when we update a job, the agent that is assigned
                #  to that job should also be updated server side to
                #  eliminate the double-call against the server.
                self.client.post_job_state(job.job_id, phase)
                self.send_agent_state(phase)
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
                        device_ip := device_info.get("device_info", {}).get(
                            "device_ip"
                        )
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
                    # TODO: in the future we will be adding more measures
                    #  of agent failure which will allow for additional
                    #  means of taking an agent out of the online mode
                    #  and generating appropriate actions to investigate
                    #  said agents.
                    if exit_code == 46:
                        comment = (
                            "Set to maintenance by agent. Recovery failed"
                            f" during job '{job.job_id}' execution."
                        )
                        # If we aren't already in maintenance mode, we will
                        # switch over to maintenance mode now due to the
                        # identification of an unrecoverable failure.
                        if self.current_mode != AgentMode.MAINTENANCE:
                            # Immediate change of operating mode, clears
                            # any pending deferred mode changes.
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

                # Send the provision logs to the server
                if phase == TestPhase.PROVISION:
                    self.client.post_provision_log(
                        job.job_id, exit_code, exit_event
                    )

                # If there was a failure in a non-test phase, end the job
                # (break out of the test phase loop and do cleanup)
                if exit_code and phase != TestPhase.TEST:
                    logger.debug("Phase %s failed, aborting job", phase)
                    job_end_reason = exit_event
                    break
        except Exception as e:
            # TODO: expose this problem to the server if we can, not just
            #  the agent logs.
            logger.exception(e)
        finally:
            # This guard exists because event_emitter is based on job_id,
            # so if an exception was thrown or no job_id was present in
            # the job_data, it's possible to get here without it being
            # defined.
            if event_emitter:
                event_emitter.emit_event(TestEvent.CLEANUP_START)

            # Always run the cleanup, even if the job was canceled or an
            # exception was thrown.
            if job and rundir:
                exit_code, _, exit_reason = job.run_test_phase(
                    TestPhase.CLEANUP, rundir
                )
            else:
                exit_code = 99
                exit_reason = "Missing `job` and/or `rundir`"
            if event_emitter:
                if exit_code:
                    logger.debug("Issue with cleanup phase: %s", exit_reason)
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
                target_path = results_basedir / rundir.name
                shutil.move(str(rundir), str(target_path))

    def retry_old_results(self):
        """Retry sending results that we previously failed to send."""
        results_dir = Path(self.client.config.get("results_basedir"))
        # List all the directories in 'results_basedir', where we store the
        # results that we couldn't transmit before
        # TODO: optimize this (don't make a list of an iterator)
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
        self.comment = "Marked agent for restart by supervisor process."
        logger.info(self.comment)
        self.needs_restart = True

    def loop(self, check_interval: int):
        """Outer agent loop.

        :check_interval: int
        :return:
        """
        # Track the current non-operational mode so we only transition once
        # per edge and call the correct exit method when the mode clears.
        while True:
            # Only check agent status and process jobs if server is available
            self.client.wait_for_server_connectivity()

            work_jobs = self.handle_mode_changes()
            t0 = time.time()

            # When agents are new or haven't been running for a while, they
            # need to re-establish their presence with the server.
            self.heartbeat_handler.update(
                self.current_mode, self.comment, self.updated_at
            )

            if work_jobs:
                self.send_agent_state(AgentState.WAITING)

                # Refresh the updated_at timestamp on advertised queues
                self.client.post_advertised_queues()
                logger.info("Checking jobs")

                # Process old jobs
                # TODO: add a state to the agent to represent this phase of
                #  execution if it is ever found to be blocking
                self.retry_old_results()

                # If processing old jobs took longer than a typical wait cycle
                # then we will skip to the next iteration of the loop to
                # re-evaluate if the mode has changed instead of processing
                # new jobs
                if time.time() - t0 > check_interval:
                    continue

                # Finally, after we know that the current state indcates that
                # jobs should be processed and all the old results have been
                # transmitted, process new jobs
                self.process_one_job()

                # After processing one job, we must check what mode to be in
                # this is done at the top of a loop, after a delay (if needed)

            # if we spent more than enough time already waiting since the last
            # mode check we can skip the sleep and get right back to talking
            # to the server at the top of the loop
            if time.time() - t0 < check_interval:
                logger.info("Sleeping for %d", check_interval)
                time.sleep(check_interval)
