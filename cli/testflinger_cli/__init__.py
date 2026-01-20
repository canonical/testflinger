# PYTHON_ARGCOMPLETE_OK
# Copyright (C) 2017-2022 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

"""TestflingerCli module."""

import contextlib
import inspect
import json
import logging
import os
import sys
import tarfile
import tempfile
import time
from argparse import ArgumentParser
from collections import Counter
from datetime import datetime, timezone
from functools import partial
from http import HTTPStatus
from pathlib import Path
from typing import Optional

import argcomplete
import requests
import yaml

from testflinger_cli import (
    autocomplete,
    client,
    config,
    consts,
    errors,
    helpers,
    history,
)
from testflinger_cli.admin import TestflingerAdminCLI
from testflinger_cli.auth import TestflingerCliAuth
from testflinger_cli.enums import LogType, TestPhase
from testflinger_cli.errors import (
    AttachmentError,
    CredentialsError,
    NetworkError,
    SnapPrivateFileError,
    UnknownStatusError,
)

logger = logging.getLogger(__name__)

# Make it easier to run from a checkout
basedir = os.path.abspath(os.path.join(__file__, ".."))
if os.path.exists(os.path.join(basedir, "setup.py")):
    sys.path.insert(0, basedir)


def cli():
    """Generate the TestflingerCli instance and run it."""
    tfcli = TestflingerCli()
    logging.basicConfig(
        level=logging.WARNING,
        format=consts.LOG_FORMAT,
        datefmt=consts.LOG_DATE_FORMAT,
    )
    try:
        tfcli.run()
    except KeyboardInterrupt:
        sys.exit("Received KeyboardInterrupt")
    except (CredentialsError, NetworkError) as exc:
        sys.exit(exc)


class TestflingerCli:
    """Class for handling the Testflinger CLI."""

    def __init__(self):
        self.history = history.TestflingerCliHistory()
        self.get_args()
        self.config = config.TestflingerCliConfig(self.args.configfile)
        server = (
            self.args.server
            or self.config.get("server")
            or os.environ.get("TESTFLINGER_SERVER")
            or consts.TESTFLINGER_SERVER
        )
        self.client_id = (
            getattr(self.args, "client_id", None)
            or self.config.get("client_id")
            or os.environ.get("TESTFLINGER_CLIENT_ID")
        )
        self.secret_key = (
            getattr(self.args, "secret_key", None)
            or self.config.get("secret_key")
            or os.environ.get("TESTFLINGER_SECRET_KEY")
        )
        error_threshold = (
            self.config.get("error_threshold")
            or os.environ.get("TESTFLINGER_ERROR_THRESHOLD")
            or consts.TESTFLINGER_ERROR_THRESHOLD
        )

        # Allow config subcommand without worrying about server or client
        if hasattr(self.args, "func") and self.args.func == self.configure:
            return
        if not server.startswith(("http://", "https://")):
            sys.exit(
                'Server must start with "http://" or "https://" '
                f'- currently set to: "{server}"'
            )
        self.client = client.Client(server, error_threshold=error_threshold)
        self.auth = TestflingerCliAuth(
            self.client_id, self.secret_key, self.client
        )

    def run(self):
        """Run the subcommand specified in command line arguments."""
        if not hasattr(self.args, "func"):
            print(self.help)
            return
        self.args.func()

    def get_args(self):
        """Handle command line arguments."""
        parser = ArgumentParser()
        parser.add_argument(
            "-c",
            "--configfile",
            type=helpers.parse_filename,
            default=None,
            help="Configuration file to use",
        )
        parser.add_argument(
            "-d", "--debug", action="store_true", help="Enable debug logging"
        )
        parser.add_argument(
            "--server", default=None, help="Testflinger server to use"
        )
        subparsers = parser.add_subparsers()
        self.admin_cli = TestflingerAdminCLI(subparsers, self)
        self._add_artifacts_args(subparsers)
        self._add_cancel_args(subparsers)
        self._add_config_args(subparsers)
        self._add_jobs_args(subparsers)
        self._add_list_queues_args(subparsers)
        self._add_login_args(subparsers)
        self._add_poll_args(subparsers)
        self._add_poll_serial_args(subparsers)
        self._add_reserve_args(subparsers)
        self._add_status_args(subparsers)
        self._add_agent_status_args(subparsers)
        self._add_queue_status_args(subparsers)
        self._add_results_args(subparsers)
        self._add_show_args(subparsers)
        self._add_submit_args(subparsers)
        self._add_secret_args(subparsers)

        argcomplete.autocomplete(parser)
        try:
            self.args = parser.parse_args()
        except SnapPrivateFileError as exc:
            parser.error(exc)
        self.help = parser.format_help()

    def _add_auth_args(self, parser):
        parser.add_argument(
            "--client-id",
            "--client_id",
            default=None,
            help="Client ID to authenticate with Testflinger server",
        )
        parser.add_argument(
            "--secret-key",
            "--secret_key",
            default=None,
            help="Secret key to be used with client id for authentication",
        )

    def _add_artifacts_args(self, subparsers):
        """Command line arguments for artifacts."""
        parser = subparsers.add_parser(
            "artifacts",
            help="Download a tarball of artifacts saved for a specified job",
        )
        parser.set_defaults(func=self.artifacts)
        parser.add_argument(
            "--filename", type=helpers.parse_filename, default="artifacts.tgz"
        )
        parser.add_argument("job_id").completer = partial(
            autocomplete.job_ids_completer, history=self.history
        )

    def _add_cancel_args(self, subparsers):
        """Command line arguments for cancel."""
        parser = subparsers.add_parser(
            "cancel", help="Tell the server to cancel a specified JOB_ID"
        )
        parser.set_defaults(func=self.cancel)
        parser.add_argument("job_id").completer = partial(
            autocomplete.job_ids_completer, history=self.history
        )

    def _add_config_args(self, subparsers):
        """Command line arguments for config."""
        parser = subparsers.add_parser(
            "config", help="Get or set configuration options"
        )
        parser.set_defaults(func=self.configure)
        parser.add_argument("setting", nargs="?", help="setting=value")

    def _add_jobs_args(self, subparsers):
        """Command line arguments for jobs."""
        parser = subparsers.add_parser(
            "jobs", help="List the previously started test jobs"
        )
        parser.set_defaults(func=self.jobs)
        parser.add_argument(
            "--status",
            "-s",
            action="store_true",
            help="Include job status (may add delay)",
        )

    def _add_list_queues_args(self, subparsers):
        """Command line arguments for list-queues."""
        parser = subparsers.add_parser(
            "list-queues",
            help="List the advertised queues on the Testflinger server",
        )
        parser.set_defaults(func=self.list_queues)
        parser.add_argument(
            "--json", action="store_true", help="Print output in JSON format"
        )

    def _add_login_args(self, subparsers):
        """Command line arguments for login."""
        parser = subparsers.add_parser(
            "login",
            help="Authenticate with server",
        )
        parser.set_defaults(func=self.login)
        self._add_auth_args(parser)

    def _add_poll_args_generic(self, parser):
        """Add arguments for poll and poll-serial."""
        parser.add_argument(
            "--oneshot",
            "-o",
            action="store_true",
            help="Get latest output and exit immediately",
        )
        parser.add_argument(
            "--start_fragment",
            "-f",
            type=int,
            default=0,
            help="Start fragment",
        )
        parser.add_argument(
            "--start_timestamp",
            "-t",
            type=datetime.fromisoformat,
            help="Start timestamp",
        )
        parser.add_argument(
            "--phase",
            "-p",
            type=str,
            help="Return logs from a specific phase",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Return logs in JSON format and exit immediately",
        )
        parser.add_argument("job_id").completer = partial(
            autocomplete.job_ids_completer, history=self.history
        )

    def _add_poll_args(self, subparsers):
        """Command line arguments for poll."""
        parser = subparsers.add_parser(
            "poll", help="Poll for output from a job until it is completed"
        )
        parser.set_defaults(func=self.poll_output)
        self._add_poll_args_generic(parser)

    def _add_poll_serial_args(self, subparsers):
        """Command line arguments for poll-serial."""
        parser = subparsers.add_parser(
            "poll-serial",
            help="Poll for serial output from a job until it is completed",
        )
        parser.set_defaults(func=self.poll_serial)
        self._add_poll_args_generic(parser)

    def _add_reserve_args(self, subparsers):
        """Command line arguments for reserve."""
        parser = subparsers.add_parser(
            "reserve", help="Install and reserve a system"
        )
        parser.set_defaults(func=self.reserve)
        parser.add_argument(
            "--dry-run",
            "-d",
            action="store_true",
            help="Only show the job data, don't submit it",
        )
        parser.add_argument("--queue", "-q", help="Name of the queue to use")
        parser.add_argument(
            "--image", "-i", help="Name of the image to use for provisioning"
        )
        parser.add_argument(
            "--key",
            "-k",
            nargs="*",
            help=(
                "Ssh key(s) to use for reservation "
                "(ex: -k lp:userid -k gh:userid)"
            ),
        )

    def _add_status_args(self, subparsers):
        """Command line arguments for status."""
        parser = subparsers.add_parser(
            "status", help="Show the status of a specified JOB_ID"
        )
        parser.set_defaults(func=self.status)
        parser.add_argument("job_id").completer = partial(
            autocomplete.job_ids_completer, history=self.history
        )

    def _add_agent_status_args(self, subparsers):
        """Command line arguments for agent status."""
        parser = subparsers.add_parser(
            "agent-status", help="Show the status of a specified agent"
        )
        parser.set_defaults(func=self.agent_status)
        parser.add_argument("agent_name")
        parser.add_argument(
            "--json", action="store_true", help="Print output in JSON format"
        )

    def _add_queue_status_args(self, subparsers):
        """Command line arguments for queue status."""
        parser = subparsers.add_parser(
            "queue-status",
            help="Show the status of the agents in a specified queue",
        )
        parser.set_defaults(func=self.queue_status)
        parser.add_argument("queue_name")
        parser.add_argument(
            "--verbose",
            "-v",
            action="store_true",
            help="Show individual jobs with details",
        )
        parser.add_argument(
            "--json", action="store_true", help="Print output in JSON format"
        )

    def _add_results_args(self, subparsers):
        """Command line arguments for results."""
        parser = subparsers.add_parser(
            "results", help="Get results JSON for a completed JOB_ID"
        )
        parser.set_defaults(func=self.results)
        parser.add_argument("job_id").completer = partial(
            autocomplete.job_ids_completer, history=self.history
        )

    def _add_show_args(self, subparsers):
        """Command line arguments for show."""
        parser = subparsers.add_parser(
            "show", help="Show the requested job JSON for a specified JOB_ID"
        )
        parser.set_defaults(func=self.show)
        parser.add_argument("job_id").completer = partial(
            autocomplete.job_ids_completer, history=self.history
        )
        parser.add_argument(
            "--yaml",
            action="store_true",
            help="Print the job as a YAML document instead of a JSON object",
        )

    def _add_submit_args(self, subparsers):
        """Command line arguments for submit."""
        parser = subparsers.add_parser(
            "submit", help="Submit a new test job to the server"
        )
        parser.set_defaults(func=self.submit)
        parser.add_argument("--poll", "-p", action="store_true")
        parser.add_argument("--quiet", "-q", action="store_true")
        parser.add_argument("--wait-for-available-agents", action="store_true")
        parser.add_argument(
            "filename",
            type=partial(helpers.parse_filename, parse_stdin=True),
            help="YAML or JSON file with your job definition, '-' for stdin",
        ).completer = argcomplete.completers.FilesCompleter(
            allowednames=("*.yaml", "*.yml", "*.json")
        )
        self._add_auth_args(parser)
        relative = parser.add_mutually_exclusive_group()
        relative.add_argument(
            "--attachments-relative-to",
            dest="relative",
            help="The reference directory for relative attachment paths",
        )

    def _add_secret_args(self, subparsers):
        """Command line arguments for secret management."""
        parser = subparsers.add_parser(
            "secret", help="Manage secrets. Requires authentication"
        )
        secret_subparser = parser.add_subparsers(
            dest="secret_command", required=True
        )

        # secret write command
        write_parser = secret_subparser.add_parser(
            "write", help="Write a secret value"
        )
        write_parser.set_defaults(func=self.secret_write)
        write_parser.add_argument("path", help="Path for the secret")
        write_parser.add_argument("value", help="Value of the secret")
        self._add_auth_args(write_parser)

        # secret delete command
        delete_parser = secret_subparser.add_parser(
            "delete", help="Delete a secret"
        )
        delete_parser.set_defaults(func=self.secret_delete)
        delete_parser.add_argument(
            "path", help="Path for the secret to delete"
        )
        self._add_auth_args(delete_parser)

    def status(self):
        """Show the status of a specified JOB_ID."""
        try:
            job_state = self.get_job_state(self.args.job_id)["job_state"]
            if job_state != "unknown":
                self.history.update(self.args.job_id, job_state)
                print(job_state)
            else:
                print(
                    "Unable to retrieve job state from the server, check your "
                    "connection or try again later."
                )
        except (errors.NoJobDataError, errors.InvalidJobIdError) as exc:
            sys.exit(str(exc))

    def agent_status(self):
        """Show the status of a specified agent."""
        try:
            try:
                agent_status = self.client.get_agent_data(self.args.agent_name)
            except client.HTTPError as exc:
                if exc.status == HTTPStatus.NOT_FOUND:
                    sys.exit(f"Agent '{self.args.agent_name}' does not exist.")
                # If any other HTTP error, raise UnknownStatusError
                raise UnknownStatusError("agent") from exc
            except (IOError, ValueError) as exc:
                # For other types of network errors or JSONDecodeError
                # if we got a bad return
                logger.debug("Unable to retrieve agent state: %s", exc)
                raise UnknownStatusError("agent") from exc

        except UnknownStatusError as exc:
            sys.exit(exc)

        if self.args.json:
            # For unclear historical reasons,
            # the "name" and "state" fields were renamed,
            # so we maintain that for compatibility
            agent_status["agent"] = agent_status.pop("name")
            agent_status["status"] = agent_status.pop("state")
            output = json.dumps(agent_status, sort_keys=True)
        else:
            output = agent_status["state"]
        print(output)

    def queue_status(self):
        """Show agent and job status in a specified queue."""
        # Get agent and job status data
        agents_status = self._get_agents_status()
        jobs_status = self._get_jobs_status()

        if self.args.json:
            output = self._queue_status_format_json_output(
                agents_status, jobs_status
            )
        else:
            output = self._queue_status_format_human_output(
                agents_status, jobs_status
            )

        print(output)

    def _get_agents_status(self):
        """Retrieve the status of the agents in a specified queue."""
        try:
            try:
                agents_status = self.client.get_agent_status_by_queue(
                    self.args.queue_name
                )
                return agents_status
            except client.HTTPError as exc:
                if exc.status == HTTPStatus.NO_CONTENT:
                    sys.exit(
                        "No agent is listening on "
                        f"queue '{self.args.queue_name}'."
                    )
                if exc.status == HTTPStatus.NOT_FOUND:
                    # Error message is specified on server side
                    sys.exit(exc.msg)
                # If any other HTTP error, raise UnknownStatusError
                raise UnknownStatusError("queue") from exc
            except (IOError, ValueError) as exc:
                # For other types of network errors or JSONDecodeError
                # if we got a bad return
                logger.debug("Unable to retrieve agent state: %s", exc)
                raise UnknownStatusError("queue") from exc

        except UnknownStatusError as exc:
            sys.exit(exc)

    def _get_jobs_status(self):
        """Retrieve the status of jobs in a specified queue."""
        try:
            jobs_data = self.client.get_jobs_on_queue(self.args.queue_name)
        except client.HTTPError as exc:
            if exc.status == HTTPStatus.NO_CONTENT:
                jobs_data = []
            else:
                logger.debug("Unable to retrieve job data: %s", exc)
                jobs_data = []
        except (IOError, ValueError) as exc:
            logger.debug("Unable to retrieve job data: %s", exc)
            jobs_data = []

        # Categorize jobs based on completion outcome
        jobs_waiting = []
        jobs_running = []
        jobs_completed = []

        for job in jobs_data:
            # Handle MongoDB date structure or plain string
            created_at = job.get("created_at", "")
            if isinstance(created_at, dict) and "$date" in created_at:
                created_at = created_at["$date"]

            job_info = {
                "job_id": job["job_id"],
                "created_at": created_at,
            }

            job_state = job.get("job_state", "").lower()
            if job_state == "waiting":
                jobs_waiting.append(job_info)
            elif job_state == "complete":
                jobs_completed.append(job_info)
            elif job_state not in ("cancelled",):  # Ignore cancelled jobs
                # All non-waiting, non-complete, non-cancelled are "running"
                jobs_running.append(job_info)

        return {
            "jobs_waiting": jobs_waiting,
            "jobs_running": jobs_running,
            "jobs_completed": jobs_completed,
        }

    def _queue_status_format_json_output(self, agents_status, jobs_status):
        """Format queue status output as JSON."""
        output_data = {
            "queue": self.args.queue_name,
            "agents": agents_status,
        }

        if self.args.verbose:
            # In verbose mode, include all job details
            output_data.update(jobs_status)
        else:
            # In non-verbose mode, only include waiting jobs
            output_data["jobs_waiting"] = jobs_status["jobs_waiting"]
        return json.dumps(output_data, indent=2)

    def _queue_status_format_human_output(self, agents_status, jobs_status):
        """Format queue status output for human reading."""
        # Get agent status count
        agents = Counter(
            (
                agent["status"]
                if agent["status"] in ("waiting", "offline")
                else "busy"
            )
            for agent in agents_status
        )

        output_lines = [
            f"Agents in queue: {agents.total()}",
            f"Available:       {agents['waiting']}",
            f"Busy:            {agents['busy']}",
            f"Offline:         {agents['offline']}",
        ]

        if self.args.verbose:
            # Add individual job details
            for job_type, jobs in jobs_status.items():
                if jobs:  # Only show if there are jobs
                    job_type_display = job_type.replace("_", " ").title()
                    output_lines.append(f"\n{job_type_display}:")
                    for job in jobs:
                        timestamp = helpers.format_timestamp(
                            job.get("created_at", "")
                        )
                        output_lines.append(f"  {job['job_id']} - {timestamp}")
        else:
            output_lines.extend(
                [
                    f"Jobs waiting:    {len(jobs_status['jobs_waiting'])}",
                    f"Jobs running:    {len(jobs_status['jobs_running'])}",
                    f"Jobs completed:  {len(jobs_status['jobs_completed'])}",
                ]
            )

        return "\n".join(output_lines)

    def cancel(self, job_id=None):
        """Tell the server to cancel a specified JOB_ID."""
        if not job_id:
            try:
                job_id = self.args.job_id
            except AttributeError:
                sys.exit("No job id specified to cancel.")
        try:
            self.client.post(f"/v1/job/{job_id}/action", {"action": "cancel"})
            self.history.update(job_id, "cancelled")
        except client.HTTPError as exc:
            if exc.status == HTTPStatus.BAD_REQUEST:
                sys.exit(
                    "Invalid job ID specified or the job is already "
                    "completed/cancelled."
                )
            raise

    def configure(self):
        """Print or set configuration values."""
        if self.args.setting:
            setting = self.args.setting.split("=")
            if len(setting) == 2:
                self.config.set(*setting)
                return
            if len(setting) == 1:
                print(f"{setting[0]} = {self.config.get(setting[0])}")
                return
        print("Current Configuration")
        print("---------------------")
        for k, v in self.config.data.items():
            print(f"{k} = {v}")
        print()

    @staticmethod
    def extract_attachment_data(job_data: dict) -> Optional[dict]:
        """Pull together the attachment data per phase from the `job_data`."""
        attachments = {}
        for phase in ("provision", "firmware_update", "test"):
            with contextlib.suppress(KeyError):
                attachments[phase] = [
                    attachment
                    for attachment in job_data[f"{phase}_data"]["attachments"]
                    if attachment.get("local")
                ]
        return attachments or None

    def pack_attachments(self, archive: str, attachment_data: dict):
        """Pack the attachments specifed by `attachment_data` into `archive`.

        Use `tarfile` instead of `shutil` because:
        > [it] handles directories, regular files, hardlinks, symbolic links,
        > fifos, character devices and block devices and is able to acquire
        > and restore file information like timestamp, access permissions and
        > owner.
        Ref: https://docs.python.org/3/library/tarfile.html
        """
        # determine the reference directory for relative attachment paths
        if self.args.relative:
            # provided as a command-line argument
            reference = Path(self.args.relative).resolve(strict=True)
        elif not self.args.filename:
            # no job file provided: use the current working directory
            reference = Path(".").resolve(strict=True)
        else:
            # retrieved from the directory where the job file is contained
            reference = self.args.filename.parent.resolve(strict=True)

        with tarfile.open(archive, "w:gz") as tar:
            for phase, attachments in attachment_data.items():
                phase_path = Path(phase)
                for attachment in attachments:
                    local_path = Path(attachment["local"])
                    if not local_path.is_absolute():
                        # make relative attachment path absolute
                        local_path = reference / local_path
                    local_path = local_path.resolve()
                    # determine the archive path for the attachment
                    # (essentially: the destination path on the agent host)
                    try:
                        agent_path = Path(attachment["agent"])
                        if agent_path.is_absolute():
                            # strip leading '/' from absolute path
                            agent_path = agent_path.relative_to(
                                agent_path.root
                            )
                    except KeyError:
                        # no agent path provided: determine it from local path
                        try:
                            # make agent path relative to the reference path
                            agent_path = local_path.relative_to(reference)
                        except ValueError:
                            # unable to determine the agent path (cannot make
                            # the local path relative to the reference path):
                            # just use the filename
                            agent_path = local_path.name
                    archive_path = phase_path / agent_path
                    try:
                        tar.add(local_path, arcname=archive_path)
                    except FileNotFoundError as exc:
                        if (
                            helpers.is_snap()
                            and helpers.file_is_in_snap_private_dir(local_path)
                        ):
                            raise SnapPrivateFileError(local_path) from exc
                        raise
                    # side effect: strip "local" information
                    attachment["agent"] = str(agent_path)
                    del attachment["local"]

    def submit(self):
        """Submit a new test job to the server."""
        if not self.args.filename:
            data = sys.stdin.read()
        else:
            try:
                data = self.args.filename.read_text(
                    encoding="utf-8", errors="ignore"
                )
            except (PermissionError, FileNotFoundError):
                logger.exception("Cannot read file %s", self.args.filename)
                sys.exit(1)
        job_dict = yaml.safe_load(data)

        # Check if agents are available to handle this queue
        # and warn or exit depending on options
        try:
            queue = job_dict["job_queue"]
        except KeyError:
            sys.exit("Error: Queue was not specified in job")
        self.check_online_agents_available(queue)

        attachments_data = self.extract_attachment_data(job_dict)
        if attachments_data is None:
            # submit job, no attachments
            job_id = self.submit_job_data(job_dict)
        else:
            with tempfile.NamedTemporaryFile(suffix="tar.gz") as archive:
                archive_path = Path(archive.name)
                # create attachments archive prior to job submission
                logger.info("Packing attachments into %s", archive_path)
                self.pack_attachments(archive_path, attachments_data)
                # submit job, followed by the submission of the archive
                job_id = self.submit_job_data(job_dict)
                try:
                    logger.info("Submitting attachments for %s", job_id)
                    self.submit_job_attachments(job_id, path=archive_path)
                except AttachmentError:
                    self.cancel(job_id)
                    sys.exit(
                        f"Job {job_id} submitted and cancelled: "
                        "failed to submit attachments"
                    )

        self.history.new(job_id, queue)
        if self.args.quiet:
            print(job_id)
        else:
            print("Job submitted successfully!")
            print(f"job_id: {job_id}")
        if self.args.poll:
            self.do_poll(job_id)

    def check_online_agents_available(self, queue: str):
        """Exit or warn if no online agents available for a specified queue."""
        try:
            agents = self.client.get_agents_on_queue(queue)
        except client.HTTPError as exc:
            if exc.status == HTTPStatus.NOT_FOUND:
                sys.exit(exc.msg)
            agents = []
        online_agents = [
            agent for agent in agents if agent["state"] != "offline"
        ]
        if len(online_agents) > 0:
            # If there are online agents, then we can proceed
            return
        if not self.args.wait_for_available_agents:
            print(
                f"ERROR: No online agents available for queue {queue}. "
                "If you want to wait for agents to become available, use the "
                "--wait-for-available-agents option."
            )
            sys.exit(1)
        print(
            f"WARNING: No online agents available for queue {queue}. "
            "Waiting for agents to become available..."
        )

    def submit_job_data(self, data: dict):
        """Submit data that was generated or read from a file as a test job."""
        retry_count = 0
        while True:
            try:
                auth_headers = self.auth.build_headers()
                job_id = self.client.submit_job(data, headers=auth_headers)
                break
            except CredentialsError as auth_exc:
                sys.exit(auth_exc)
            except client.HTTPError as exc:
                if exc.status == HTTPStatus.BAD_REQUEST:
                    sys.exit(
                        "The job you submitted contained bad data or "
                        "bad formatting, or did not specify a "
                        "job_queue."
                    )
                if exc.status == HTTPStatus.FORBIDDEN:
                    sys.exit(
                        "Received 403 error from server with reason: "
                        f"{exc.msg}\n"
                        "The specified client credentials do not have "
                        "sufficient permissions for the resource(s) "
                        "you are trying to access."
                    )
                if exc.status == HTTPStatus.UNAUTHORIZED:
                    if "expired" in exc.msg:
                        if retry_count < 2:
                            retry_count += 1
                            self.auth.refresh_authentication()
                        else:
                            sys.exit(
                                "Received 401 error from server due to "
                                "expired authorization token."
                            )
                    else:
                        sys.exit(
                            "Received 401 error from server with reason: "
                            f"{exc.msg}\n"
                            "You are attempting to use a feature "
                            "that requires client authorisation "
                            "without using client credentials. \n"
                            "See https://testflinger.readthedocs.io/en/latest"
                            "/how-to/authentication.html for more details"
                        )
                else:
                    # This shouldn't happen, so let's get more information
                    sys.exit(
                        "Unexpected error status from testflinger "
                        f"server: [{exc.status}] {exc.msg}"
                    )
        return job_id

    def submit_job_attachments(self, job_id: str, path: Path):
        """Submit attachments archive for a job to the server.

        :param job_id:
            ID for the test job
        :param path:
            The path to the attachment archive
        """
        # defaults for retries
        wait = self.config.get("attachments_retry_wait", 10)
        timeout = self.config.get("attachments_timeout", 600)
        tries = self.config.get("attachments_tries", 3)

        for _ in range(tries):
            try:
                self.client.post_attachment(job_id, path, timeout=timeout)
            except KeyboardInterrupt as error:
                raise AttachmentError(
                    f"Unable to submit attachment archive for {job_id}: "
                    f"attachment upload was cancelled by the user"
                ) from error
            except requests.HTTPError as error:
                # we can't recover from these errors, give up without retrying
                if error.response.status_code == HTTPStatus.BAD_REQUEST:
                    raise AttachmentError(
                        f"Unable to submit attachment archive for {job_id}: "
                        f"{error.response.text}"
                    ) from error
                # This shouldn't happen, so let's get more information
                sys.exit(
                    "Unexpected error status from testflinger server "
                    f"({error.response.status_code}): {error.response.text}"
                )
            except (requests.Timeout, requests.ConnectionError):
                # recoverable errors, try again
                time.sleep(wait)
                wait *= 1.3
            else:
                # success
                return

        # having reached this point, all tries have failed
        raise AttachmentError(
            f"Unable to submit attachment archive for {job_id}: "
            f"failed after {tries} tries"
        )

    def show(self):
        """Show the requested job JSON for a specified JOB_ID."""
        try:
            results = self.client.show_job(self.args.job_id)
        except client.HTTPError as exc:
            if exc.status == HTTPStatus.NO_CONTENT:
                sys.exit("No data found for that job id.")
            if exc.status == HTTPStatus.BAD_REQUEST:
                sys.exit(
                    "Invalid job id specified. Check the job id "
                    "to be sure it is correct"
                )
            # This shouldn't happen, so let's get more information
            logger.error(
                "Unexpected error status from testflinger server: %s",
                exc.status,
            )
            sys.exit(1)
        if self.args.yaml:
            to_print = helpers.pretty_yaml_dump(
                results, sort_keys=True, indent=4, default_flow_style=False
            )
        else:
            to_print = json.dumps(results, sort_keys=True, indent=4)
        print(to_print)

    def results(self):
        """Get results JSON for a completed JOB_ID."""
        try:
            results = self.client.get_results(self.args.job_id)
        except client.HTTPError as exc:
            if exc.status == HTTPStatus.NO_CONTENT:
                sys.exit("No results found for that job id.")
            if exc.status == HTTPStatus.NOT_FOUND:
                sys.exit(
                    "Invalid job id specified. Check the job id "
                    "to be sure it is correct"
                )
            # This shouldn't happen, so let's get more information
            logger.error(
                "Unexpected error status from testflinger server: %s",
                exc.status,
            )
            sys.exit(1)

        print(json.dumps(results, sort_keys=True, indent=4))

    def artifacts(self):
        """Download a tarball of artifacts saved for a specified job."""
        print("Downloading artifacts tarball...")
        try:
            self.client.get_artifact(self.args.job_id, self.args.filename)
        except client.HTTPError as exc:
            if exc.status == HTTPStatus.NO_CONTENT:
                sys.exit("No artifacts tarball found for that job id.")
            if exc.status == HTTPStatus.BAD_REQUEST:
                sys.exit(
                    "Invalid job id specified. Check the job id "
                    "to be sure it is correct"
                )
            # This shouldn't happen, so let's get more information
            logger.error(
                "Unexpected error status from testflinger server: %s",
                exc.status,
            )
            sys.exit(1)
        print(f"Artifacts downloaded to {self.args.filename}")

    def _get_combined_log_output(
        self,
        job_id: str,
        log_type: LogType,
        phase: str = None,
        start_fragment: int = 0,
        start_timestamp=None,
    ):
        """
        Return last fragment number and combined logs for specified phase
        or for all phases if unspecified.
        """
        output_json = self.client.get_logs(
            job_id,
            log_type,
            phase,
            start_fragment,
            start_timestamp,
        )
        log_dict = output_json[log_type]
        if phase:
            return (
                log_dict[phase]["last_fragment_number"],
                log_dict[phase]["log_data"],
            )

        log_tuples = [
            (phase_logs["last_fragment_number"], phase_logs["log_data"])
            for phase in TestPhase
            if (phase_logs := log_dict.get(phase.value))
        ]
        if not log_tuples:
            return -1, ""
        fragment_numbers, log_data_list = zip(*log_tuples, strict=False)
        last_fragment_number = max(fragment_numbers)
        combined_logs = "".join(log_data_list)
        return last_fragment_number, combined_logs

    def poll(self, log_type: LogType):
        """Poll for output from a job until it is completed."""
        start_fragment = self.args.start_fragment
        start_timestamp = self.args.start_timestamp
        job_id = self.args.job_id
        phase = self.args.phase
        if self.args.oneshot:
            # This could get an IOError for connection errors or timeouts
            # Raise it since it's not running continuously in this mode
            last_fragment_number, log_data = self._get_combined_log_output(
                job_id, log_type, phase, start_fragment, start_timestamp
            )

            if last_fragment_number < 0:
                print("Waiting on Output")
            else:
                print(log_data, end="", flush=True)
                print(f"Last Fragment Number: {last_fragment_number}")
            sys.exit(0)
        if self.args.json:
            output_json = self.client.get_logs(
                job_id,
                log_type,
                phase,
                start_fragment,
                start_timestamp,
            )
            print(json.dumps(output_json, indent=4))
            sys.exit(0)

        self.do_poll(job_id, log_type)

    def poll_output(self):
        """Poll for agent output from a job until it is completed."""
        self.poll(LogType.STANDARD_OUTPUT)

    def poll_serial(self):
        """Poll for serial output from a job until it is completed."""
        self.poll(LogType.SERIAL_OUTPUT)

    def do_poll(
        self,
        job_id: str,
        log_type: LogType = LogType.STANDARD_OUTPUT,
    ):
        """Poll for output from a running job and print it while it runs.

        :param str job_id: Job ID
        :param LogType log_type: Enum representing serial or agent output.
        """
        start_fragment = getattr(self.args, "start_fragment", 0)
        start_timestamp = getattr(self.args, "start_timestamp", None)
        phase = getattr(self.args, "phase", None)

        try:
            job_state_data = self.get_job_state(job_id)
        except (errors.NoJobDataError, errors.InvalidJobIdError) as exc:
            sys.exit(str(exc))
        job_state = job_state_data["job_state"]
        self.history.update(job_id, job_state)
        prev_queue_pos = None
        if job_state == "waiting":
            print("This job is waiting on a node to become available.")
        cur_fragment = start_fragment
        consecutive_empty_polls = 0
        while True:
            try:
                job_state_data = self.get_job_state(job_id)
                job_state = job_state_data["job_state"]

                self.history.update(job_id, job_state)
                last_fragment_number, log_data = self._get_combined_log_output(
                    job_id, log_type, phase, cur_fragment, start_timestamp
                )

                # Print logs before any check
                if last_fragment_number >= 0 and log_data:
                    print(log_data, end="", flush=True)
                    cur_fragment = last_fragment_number + 1
                    consecutive_empty_polls = 0
                else:
                    consecutive_empty_polls += 1
                    if consecutive_empty_polls == 9:
                        consecutive_empty_polls = 0
                        print("Waiting on output...", file=sys.stderr)

                if phase:
                    phase_status = job_state_data.get(phase)
                    if phase_status is not None:
                        print(
                            f"\nPhase '{phase}' completed with "
                            f"exit code: {phase_status}",
                            file=sys.stderr,
                        )
                        print(
                            f"Use 'testflinger poll {job_id} --start_fragment "
                            f"{cur_fragment}' to continue polling.",
                            file=sys.stderr,
                        )
                        break

                if job_state in ("cancelled", "complete", "completed"):
                    break

                if job_state == "waiting":
                    queue_pos = int(self.client.get_job_position(job_id))
                    if queue_pos != prev_queue_pos:
                        prev_queue_pos = queue_pos
                        if queue_pos == 0:
                            print(
                                "This job will be picked up after the "
                                "current job is complete (it is next in line)"
                            )
                        else:
                            print(
                                f"This job will be picked up after the "
                                f"current job and {queue_pos} job(s) ahead "
                                f"of it in the queue are complete"
                            )
                time.sleep(10)
            except (errors.NoJobDataError, errors.InvalidJobIdError):
                # Job-specific errors should exit immediately
                raise
            except (IOError, client.HTTPError):
                # Ignore/retry or debug any connection errors or timeouts
                if self.args.debug:
                    logger.exception("Error polling for job output")
            except KeyboardInterrupt:
                choice = input(
                    f"\nCancel job {job_id} before exiting "
                    "(y)es/(N)o/(c)ontinue? "
                )
                if choice:
                    choice = choice[0].lower()
                    if choice == "c":
                        continue
                    if choice == "y":
                        self.cancel(job_id)
                print(f"\nNext fragment number: {cur_fragment}")
                # Both y and n will allow the external handler deal with it
                raise

        print(job_state)

    def jobs(self):
        """List the previously started test jobs."""
        # Getting job state may be slow, only include if requested
        status_text = "Status" if self.args.status else ""
        print(f"{'Job ID':36} {status_text:9} Submission Time  Queue")
        print("-" * 79)
        for job_id, jobdata in self.history.history.items():
            if self.args.status:
                job_state = jobdata.get("job_state")
                if job_state not in ("cancelled", "complete", "completed"):
                    try:
                        job_state = self.get_job_state(job_id)["job_state"]
                        self.history.update(job_id, job_state)
                    except (
                        errors.NoJobDataError,
                        errors.InvalidJobIdError,
                        IOError,
                        ValueError,
                    ):
                        # Handle errors gracefully for job listings
                        job_state = "unknown"
            else:
                job_state = ""
            timestamp = datetime.fromtimestamp(
                jobdata.get("submission_time"), tz=timezone.utc
            )
            queue = jobdata["queue"]
            print(f"{job_id} {job_state:9} {timestamp:%a %b %d %H:%M} {queue}")
        print()

    def list_queues(self):
        """List the advertised queues on the current Testflinger server."""
        queues = self.do_list_queues()
        if self.args.json:
            print(json.dumps(queues))
        else:
            print("Advertised queues on this server:")
            for name, description in sorted(queues.items()):
                print(f" {name} - {description}")

    def reserve(self):
        """Install and reserve a system."""
        queues = self.do_list_queues()
        queue = self.args.queue or helpers.prompt_for_queue(queues)
        if queue not in queues:
            logger.warning("'%s' is not in the list of known queues", queue)
        try:
            images = self.client.get_images(queue)
        except OSError:
            logger.warning("Unable to get a list of images from the server!")
            images = {}
        image = self.args.image or helpers.prompt_for_image(images)
        if (
            not image.startswith(("http://", "https://"))
            and image not in images
        ):
            logger.error("'%s' is not in the list of known images", image)
        if image.startswith(("http://", "https://")):
            image = "url: " + image
        else:
            image = images[image]
        ssh_keys = self.args.key or helpers.prompt_for_ssh_keys()
        for ssh_key in ssh_keys:
            if not ssh_key.startswith("lp:") and not ssh_key.startswith("gh:"):
                logger.error("Invalid SSH key format: %s", ssh_key)
        template = inspect.cleandoc(
            """job_queue: {queue}
                                    provision_data:
                                        {image}
                                    reserve_data:
                                        ssh_keys:"""
        )
        for ssh_key in ssh_keys:
            template += f"\n      - {ssh_key}"
        job_data = template.format(queue=queue, image=image)
        print("\nThe following yaml will be submitted:")
        print(job_data)
        if self.args.dry_run:
            return
        answer = input("Proceed? (Y/n) ")
        if answer in ("Y", "y", ""):
            job_id = self.submit_job_data(job_data)
            print("Job submitted successfully!")
            print(f"job_id: {job_id}")
            self.do_poll(job_id)

    def do_list_queues(self) -> dict[str, str]:
        """List the advertised queues on the Testflinger server.

        :return: A dictionary of queue names and their descriptions.
        """
        logger.warning(
            "This only shows a curated list of queues with descriptions"
        )
        try:
            queues = self.client.get_queues()
        except client.HTTPError:
            logger.exception("Unable to get a list of queues from the server.")
            return {}
        return queues

    def get_job_state(self, job_id: str) -> dict:
        """Return the job state for the specified job_id.

        :param job_id: Job ID
        :raises NoJobDataError: When HTTP 204 (no data found)
        :raises InvalidJobIdError: When HTTP 400 (invalid job ID)
        :raises IOError: When network error occurs
        :raises ValueError: When response cannot be parsed
        :return: Job and phase statuses
        """
        try:
            return self.client.get_status(job_id)
        except client.HTTPError as exc:
            if exc.status == HTTPStatus.NO_CONTENT:
                raise errors.NoJobDataError() from exc
            if exc.status == HTTPStatus.BAD_REQUEST:
                raise errors.InvalidJobIdError() from exc
            # For other HTTP errors, log and return unknown state
            logger.debug("HTTP error retrieving job state: %s", exc)
        except (IOError, ValueError) as exc:
            # For other types of network errors, or JSONDecodeError if we got
            # a bad return from get_status()
            logger.debug("Unable to retrieve job state: %s", exc)
        return {"job_state": "unknown"}

    def login(self):
        """Authenticate using refresh_token or provided credentials."""
        # Clear refresh token if user is attempting reauthentication
        self.auth.clear_refresh_token()
        try:
            # Since refresh token was cleared, credentials are always needed
            if self.auth.authenticate():
                print(f"Successfully authenticated as user '{self.client_id}'")
            else:
                # authenticate can return None if no credentials were provided
                sys.exit("Please provide credentials and reattempt login")
        except CredentialsError as exc:
            sys.exit(exc)

    def secret_write(self):
        """Write a secret value for the authenticated client."""
        try:
            auth_headers = self.auth.build_headers()
        except CredentialsError as exc:
            sys.exit(exc)

        if auth_headers is None or self.client_id is None:
            sys.exit("Error writing secret: Authentication is required")

        secret_data = {"value": self.args.value}
        endpoint = f"/v1/secrets/{self.client_id}/{self.args.path}"
        try:
            self.client.put(endpoint, secret_data, headers=auth_headers)
        except client.HTTPError as exc:
            sys.exit(f"Error writing secret: [{exc.status}] {exc.msg}")
        print(f"Secret '{self.args.path}' written successfully")

    def secret_delete(self):
        """Delete a secret for the authenticated client."""
        try:
            auth_headers = self.auth.build_headers()
        except CredentialsError as exc:
            sys.exit(exc)

        if auth_headers is None or self.client_id is None:
            sys.exit("Error deleting secret: Authentication is required")

        endpoint = f"/v1/secrets/{self.client_id}/{self.args.path}"
        try:
            self.client.delete(endpoint, headers=auth_headers)
        except client.HTTPError as exc:
            sys.exit(f"Error deleting secret: [{exc.status}] {exc.msg}")
        print(f"Secret '{self.args.path}' deleted successfully")
