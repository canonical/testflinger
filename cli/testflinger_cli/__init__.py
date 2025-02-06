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

"""
TestflingerCli module
"""


import inspect
import json
import logging
import os
import sys
import tarfile
import tempfile
import time
from argparse import ArgumentParser
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Optional

import argcomplete
import requests
import yaml

from testflinger_cli import autocomplete, client, config, history

logger = logging.getLogger(__name__)

# Make it easier to run from a checkout
basedir = os.path.abspath(os.path.join(__file__, ".."))
if os.path.exists(os.path.join(basedir, "setup.py")):
    sys.path.insert(0, basedir)


def cli():
    """Generate the TestflingerCli instance and run it"""
    try:
        tfcli = TestflingerCli()
        configure_logging()
        tfcli.run()
    except KeyboardInterrupt:
        sys.exit("Received KeyboardInterrupt")


def configure_logging():
    """Configure default logging"""
    logging.basicConfig(
        level=logging.WARNING,
        format=(
            "%(levelname)s: %(asctime)s %(filename)s:%(lineno)d -- %(message)s"
        ),
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _get_image(images):
    """Ask the user to select an image from a list"""
    image = ""
    flex_url = ""
    if images and images[list(images.keys())[0]].startswith("url:"):
        # If this device can take URLs, offer to let the user enter one
        # instead of just using the known images
        flex_url = "or URL for a valid image starting with http(s)://... "
    while not image or image == "?":
        image = input(
            "\nEnter the name of the image you want to use "
            + flex_url
            + "('?' to list) "
        )
        if image == "?":
            if not images:
                print(
                    "WARNING: There are no images defined for this "
                    "device. You may also provide the URL to an image "
                    "that can be booted with this device though."
                )
                continue
            for image_id in sorted(images.keys()):
                print(" " + image_id)
            continue
        if image.startswith(("http://", "https://")):
            return image
        if image not in images.keys():
            print(
                "ERROR: '{}' is not in the list of known images for "
                "that queue, please select another.".format(image)
            )
            image = ""
    return image


def _get_ssh_keys():
    ssh_keys = ""
    while not ssh_keys.strip():
        ssh_keys = input(
            "\nEnter the ssh key(s) you wish to use: "
            "(ex: lp:userid, gh:userid) "
        )
        key_list = [ssh_key.strip() for ssh_key in ssh_keys.split(",")]
        for ssh_key in key_list:
            if not ssh_key.startswith("lp:") and not ssh_key.startswith("gh:"):
                ssh_keys = ""
                print("Please enter keys in the form lp:userid or gh:userid")
    return key_list


def _print_queue_message():
    print(
        "ATTENTION: This only shows a curated list of queues with "
        "descriptions, not ALL queues. If you can't find the queue you want "
        "to use, a job can still be submitted for queues not listed here.\n"
    )


class AttachmentError(Exception):
    """Exception thrown when attachments fail to be submitted"""


# pylint: disable=R0904
class TestflingerCli:
    """Class for handling the Testflinger CLI"""

    def __init__(self):
        self.history = history.TestflingerCliHistory()
        self.get_args()
        self.config = config.TestflingerCliConfig(self.args.configfile)
        server = (
            self.args.server
            or self.config.get("server")
            or os.environ.get("TESTFLINGER_SERVER")
            or "https://testflinger.canonical.com"
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
            or 3
        )

        # Allow config subcommand without worrying about server or client
        if (
            hasattr(self.args, "func")
            and self.args.func == self.configure  # pylint: disable=W0143
        ):
            return
        if not server.startswith(("http://", "https://")):
            sys.exit(
                'Server must start with "http://" or "https://" '
                '- currently set to: "{}"'.format(server)
            )
        self.client = client.Client(server, error_threshold=error_threshold)

    def run(self):
        """Run the subcommand specified in command line arguments"""
        if hasattr(self.args, "func"):
            sys.exit(self.args.func())
        print(self.help)

    def get_args(self):
        """Handle command line arguments"""
        parser = ArgumentParser()
        parser.add_argument(
            "-c",
            "--configfile",
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
        self._add_artifacts_args(subparsers)
        self._add_cancel_args(subparsers)
        self._add_config_args(subparsers)
        self._add_jobs_args(subparsers)
        self._add_list_queues_args(subparsers)
        self._add_poll_args(subparsers)
        self._add_reserve_args(subparsers)
        self._add_status_args(subparsers)
        self._add_results_args(subparsers)
        self._add_show_args(subparsers)
        self._add_submit_args(subparsers)

        argcomplete.autocomplete(parser)
        self.args = parser.parse_args()
        self.help = parser.format_help()

    def _add_artifacts_args(self, subparsers):
        """Command line arguments for artifacts"""
        parser = subparsers.add_parser(
            "artifacts",
            help="Download a tarball of artifacts saved for a specified job",
        )
        parser.set_defaults(func=self.artifacts)
        parser.add_argument("--filename", default="artifacts.tgz")
        parser.add_argument("job_id").completer = partial(
            autocomplete.job_ids_completer, history=self.history
        )

    def _add_cancel_args(self, subparsers):
        """Command line arguments for cancel"""
        parser = subparsers.add_parser(
            "cancel", help="Tell the server to cancel a specified JOB_ID"
        )
        parser.set_defaults(func=self.cancel)
        parser.add_argument("job_id").completer = partial(
            autocomplete.job_ids_completer, history=self.history
        )

    def _add_config_args(self, subparsers):
        """Command line arguments for config"""
        parser = subparsers.add_parser(
            "config", help="Get or set configuration options"
        )
        parser.set_defaults(func=self.configure)
        parser.add_argument("setting", nargs="?", help="setting=value")

    def _add_jobs_args(self, subparsers):
        """Command line arguments for jobs"""
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
        """Command line arguments for list-queues"""
        parser = subparsers.add_parser(
            "list-queues",
            help="List the advertised queues on the Testflinger server",
        )
        parser.set_defaults(func=self.list_queues)

    def _add_poll_args(self, subparsers):
        """Command line arguments for poll"""
        parser = subparsers.add_parser(
            "poll", help="Poll for output from a job until it is completed"
        )
        parser.set_defaults(func=self.poll)
        parser.add_argument(
            "--oneshot",
            "-o",
            action="store_true",
            help="Get latest output and exit immediately",
        )
        parser.add_argument("job_id").completer = partial(
            autocomplete.job_ids_completer, history=self.history
        )

    def _add_reserve_args(self, subparsers):
        """Command line arguments for reserve"""
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
        """Command line arguments for status"""
        parser = subparsers.add_parser(
            "status", help="Show the status of a specified JOB_ID"
        )
        parser.set_defaults(func=self.status)
        parser.add_argument("job_id").completer = partial(
            autocomplete.job_ids_completer, history=self.history
        )

    def _add_results_args(self, subparsers):
        """Command line arguments for results"""
        parser = subparsers.add_parser(
            "results", help="Get results JSON for a completed JOB_ID"
        )
        parser.set_defaults(func=self.results)
        parser.add_argument("job_id").completer = partial(
            autocomplete.job_ids_completer, history=self.history
        )

    def _add_show_args(self, subparsers):
        """Command line arguments for show"""
        parser = subparsers.add_parser(
            "show", help="Show the requested job JSON for a specified JOB_ID"
        )
        parser.set_defaults(func=self.show)
        parser.add_argument("job_id").completer = partial(
            autocomplete.job_ids_completer, history=self.history
        )

    def _add_submit_args(self, subparsers):
        """Command line arguments for submit"""
        parser = subparsers.add_parser(
            "submit", help="Submit a new test job to the server"
        )
        parser.set_defaults(func=self.submit)
        parser.add_argument("--poll", "-p", action="store_true")
        parser.add_argument("--quiet", "-q", action="store_true")
        parser.add_argument("--wait-for-available-agents", action="store_true")
        parser.add_argument("filename").completer = (
            argcomplete.completers.FilesCompleter(
                allowednames=("*.yaml", "*.yml", "*.json")
            )
        )
        parser.add_argument(
            "--client_id",
            default=None,
            help="Client ID to authenticate with Testflinger server",
        )
        parser.add_argument(
            "--secret_key",
            default=None,
            help="Secret key to be used with client id for authentication",
        )
        relative = parser.add_mutually_exclusive_group()
        relative.add_argument(
            "--attachments-relative-to",
            dest="relative",
            help="The reference directory for relative attachment paths",
        )

    def status(self):
        """Show the status of a specified JOB_ID"""
        job_state = self.get_job_state(self.args.job_id)
        if job_state != "unknown":
            self.history.update(self.args.job_id, job_state)
            print(job_state)
        else:
            print(
                "Unable to retrieve job state from the server, check your "
                "connection or try again later."
            )

    def cancel(self, job_id=None):
        """Tell the server to cancel a specified JOB_ID"""
        if not job_id:
            try:
                job_id = self.args.job_id
            except AttributeError:
                sys.exit("No job id specified to cancel.")
        try:
            self.client.put(f"/v1/job/{job_id}/action", {"action": "cancel"})
            self.history.update(job_id, "cancelled")
        except client.HTTPError as exc:
            if exc.status == 400:
                sys.exit(
                    "Invalid job ID specified or the job is already "
                    "completed/cancelled."
                )
            if exc.status == 404:
                sys.exit(
                    "Received 404 error from server. Are you "
                    "sure this is a testflinger server?"
                )
            raise

    def configure(self):
        """Print or set configuration values"""
        if self.args.setting:
            setting = self.args.setting.split("=")
            if len(setting) == 2:
                self.config.set(*setting)
                return
            if len(setting) == 1:
                print(
                    "{} = {}".format(setting[0], self.config.get(setting[0]))
                )
                return
        print("Current Configuration")
        print("---------------------")
        for k, v in self.config.data.items():
            print("{} = {}".format(k, v))
        print()

    @staticmethod
    def extract_attachment_data(job_data: dict) -> Optional[dict]:
        """Pull together the attachment data per phase from the `job_data`"""
        attachments = {}
        for phase in ("provision", "firmware_update", "test"):
            try:
                attachments[phase] = [
                    attachment
                    for attachment in job_data[f"{phase}_data"]["attachments"]
                    if attachment.get("local")
                ]
            except KeyError:
                pass
        return attachments or None

    def pack_attachments(self, archive: str, attachment_data: dict):
        """Pack the attachments specifed by `attachment_data` into `archive`

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
        else:
            # retrieved from the directory where the job file is contained
            reference = Path(self.args.filename).parent.resolve(strict=True)

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
                    tar.add(local_path, arcname=archive_path)
                    # side effect: strip "local" information
                    attachment["agent"] = str(agent_path)
                    del attachment["local"]

    def build_auth_headers(self):
        """
        Gets a JWT from the server and creates an authorization header from it
        """
        jwt = self.authenticate_with_server()
        if jwt is not None:
            auth_headers = {"Authorization": jwt}
        else:
            auth_headers = None
        return auth_headers

    def submit(self):
        """Submit a new test job to the server"""
        if self.args.filename == "-":
            data = sys.stdin.read()
        else:
            try:
                with open(
                    self.args.filename, encoding="utf-8", errors="ignore"
                ) as job_file:
                    data = job_file.read()
            except FileNotFoundError:
                sys.exit(f"File not found: {self.args.filename}")
        job_dict = yaml.safe_load(data)

        # Check if agents are available to handle this queue
        # and warn or exit depending on options
        queue = job_dict.get("job_queue")
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
            print("job_id: {}".format(job_id))
        if self.args.poll:
            self.do_poll(job_id)

    def check_online_agents_available(self, queue: str):
        """Exit or warn if no online agents available for a specified queue"""
        try:
            agents = self.client.get_agents_on_queue(queue)
        except client.HTTPError:
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
        """Submit data that was generated or read from a file as a test job"""
        retry_count = 0
        while True:
            try:
                auth_headers = self.build_auth_headers()
                job_id = self.client.submit_job(data, headers=auth_headers)
                break
            except client.HTTPError as exc:
                if exc.status == 400:
                    sys.exit(
                        "The job you submitted contained bad data or "
                        "bad formatting, or did not specify a "
                        "job_queue."
                    )
                if exc.status == 404:
                    sys.exit(
                        "Received 404 error from server. Are you "
                        "sure this is a testflinger server?"
                    )

                if exc.status == 403:
                    sys.exit(
                        "Received 403 error from server with reason "
                        f"{exc.msg}"
                        "The specified client credentials do not have "
                        "sufficient permissions for the resource(s) "
                        "you are trying to access."
                    )
                if exc.status == 401:
                    if "expired" in exc.msg:
                        if retry_count < 2:
                            retry_count += 1
                        else:
                            sys.exit(
                                "Received 401 error from server due to "
                                "expired authorization token."
                            )
                    else:
                        sys.exit(
                            "Received 401 error from server with reason "
                            f"{exc.msg} You are attempting to use a feature "
                            "that requires client authorisation "
                            "without using client credentials. "
                            "See https://testflinger.readthedocs.io/en/latest"
                            "/how-to/authentication/ for more details"
                        )
                else:
                    # This shouldn't happen, so let's get more information
                    sys.exit(
                        "Unexpected error status from testflinger "
                        f"server: [{exc.status}] {exc.msg}"
                    )
        return job_id

    def submit_job_attachments(self, job_id: str, path: Path):
        """Submit attachments archive for a job to the server

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
                if error.response.status_code == 400:
                    raise AttachmentError(
                        f"Unable to submit attachment archive for {job_id}: "
                        f"{error.response.text}"
                    ) from error
                if error.response.status_code == 404:
                    raise AttachmentError(
                        "Received 404 error from server. Are you "
                        "sure this is a testflinger server and "
                        "that it supports attachments?"
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

    def authenticate_with_server(self):
        """
        Authenticate client id and secret key with server
        and return JWT with permissions
        """
        if self.client_id is None or self.secret_key is None:
            return None

        try:
            jwt = self.client.authenticate(self.client_id, self.secret_key)
        except client.HTTPError as exc:
            if exc.status == 401:
                sys.exit(
                    "Authentication with Testflinger server failed. "
                    "Check your client id and secret key"
                )
            if exc.status == 404:
                sys.exit(
                    "Received 404 error from server. Are you "
                    "sure this is a testflinger server?"
                )
            # This shouldn't happen, so let's get more information
            logger.error(
                "Unexpected error status from testflinger server: %s",
                exc.status,
            )
            sys.exit(1)
        return jwt

    def show(self):
        """Show the requested job JSON for a specified JOB_ID"""
        try:
            results = self.client.show_job(self.args.job_id)
        except client.HTTPError as exc:
            if exc.status == 204:
                sys.exit("No data found for that job id.")
            if exc.status == 400:
                sys.exit(
                    "Invalid job id specified. Check the job id "
                    "to be sure it is correct"
                )
            if exc.status == 404:
                sys.exit(
                    "Received 404 error from server. Are you "
                    "sure this is a testflinger server?"
                )
            # This shouldn't happen, so let's get more information
            logger.error(
                "Unexpected error status from testflinger server: %s",
                exc.status,
            )
            sys.exit(1)
        print(json.dumps(results, sort_keys=True, indent=4))

    def results(self):
        """Get results JSON for a completed JOB_ID"""
        try:
            results = self.client.get_results(self.args.job_id)
        except client.HTTPError as exc:
            if exc.status == 204:
                sys.exit("No results found for that job id.")
            if exc.status == 400:
                sys.exit(
                    "Invalid job id specified. Check the job id "
                    "to be sure it is correct"
                )
            if exc.status == 404:
                sys.exit(
                    "Received 404 error from server. Are you "
                    "sure this is a testflinger server?"
                )
            # This shouldn't happen, so let's get more information
            logger.error(
                "Unexpected error status from testflinger server: %s",
                exc.status,
            )
            sys.exit(1)

        print(json.dumps(results, sort_keys=True, indent=4))

    def artifacts(self):
        """Download a tarball of artifacts saved for a specified job"""
        print("Downloading artifacts tarball...")
        try:
            self.client.get_artifact(self.args.job_id, self.args.filename)
        except client.HTTPError as exc:
            if exc.status == 204:
                sys.exit("No artifacts tarball found for that job id.")
            if exc.status == 400:
                sys.exit(
                    "Invalid job id specified. Check the job id "
                    "to be sure it is correct"
                )
            if exc.status == 404:
                sys.exit(
                    "Received 404 error from server. Are you "
                    "sure this is a testflinger server?"
                )
            # This shouldn't happen, so let's get more information
            logger.error(
                "Unexpected error status from testflinger server: %s",
                exc.status,
            )
            sys.exit(1)
        print("Artifacts downloaded to {}".format(self.args.filename))

    def poll(self):
        """Poll for output from a job until it is completed"""
        if self.args.oneshot:
            # This could get an IOError for connection errors or timeouts
            # Raise it since it's not running continuously in this mode
            output = self.get_latest_output(self.args.job_id)
            if output:
                print(output, end="", flush=True)
            sys.exit(0)
        self.do_poll(self.args.job_id)

    def do_poll(self, job_id):
        """Poll for output from a running job and print it while it runs

        :param str job_id: Job ID
        """
        job_state = self.get_job_state(job_id)
        self.history.update(job_id, job_state)
        prev_queue_pos = None
        if job_state == "waiting":
            print("This job is waiting on a node to become available.")
        while True:
            try:
                job_state = self.get_job_state(job_id)
                self.history.update(job_id, job_state)
                if job_state in ("cancelled", "complete", "completed"):
                    break
                if job_state == "waiting":
                    queue_pos = self.client.get_job_position(job_id)
                    if int(queue_pos) != prev_queue_pos:
                        prev_queue_pos = int(queue_pos)
                        print("Jobs ahead in queue: {}".format(queue_pos))
                time.sleep(10)
                output = ""
                output = self.get_latest_output(job_id)
                if output:
                    print(output, end="", flush=True)
            except (IOError, client.HTTPError):
                # Ignore/retry or debug any connection errors or timeouts
                if self.args.debug:
                    logging.exception("Error polling for job output")
            except KeyboardInterrupt:
                choice = input(
                    "\nCancel job {} before exiting "
                    "(y)es/(N)o/(c)ontinue? ".format(job_id)
                )
                if choice:
                    choice = choice[0].lower()
                    if choice == "c":
                        continue
                    if choice == "y":
                        self.cancel(job_id)
                # Both y and n will allow the external handler deal with it
                raise

        print(job_state)

    def jobs(self):
        """List the previously started test jobs"""
        if self.args.status:
            # Getting job state may be slow, only include if requested
            status_text = "Status"
        else:
            status_text = ""
        print(
            "{:36} {:9} {}  {}".format(
                "Job ID", status_text, "Submission Time", "Queue"
            )
        )
        print("-" * 79)
        for job_id, jobdata in self.history.history.items():
            if self.args.status:
                job_state = jobdata.get("job_state")
                if job_state not in ("cancelled", "complete", "completed"):
                    job_state = self.get_job_state(job_id)
                    self.history.update(job_id, job_state)
            else:
                job_state = ""
            print(
                "{} {:9} {} {}".format(
                    job_id,
                    job_state,
                    datetime.fromtimestamp(
                        jobdata.get("submission_time")
                    ).strftime("%a %b %d %H:%M"),
                    jobdata.get("queue"),
                )
            )
        print()

    def list_queues(self):
        """List the advertised queues on the current Testflinger server"""
        _print_queue_message()
        try:
            queues = self.client.get_queues()
        except client.HTTPError as exc:
            if exc.status == 404:
                sys.exit(
                    "Received 404 error from server. Are you "
                    "sure this is a testflinger server?"
                )
            logger.error("Unable to get a list of queues from the server.")
            sys.exit(1)
        print("Advertised queues on this server:")
        for name, description in sorted(queues.items()):
            print(" {} - {}".format(name, description))

    def reserve(self):
        """Install and reserve a system"""
        _print_queue_message()
        try:
            queues = self.client.get_queues()
        except OSError:
            logger.warning("Unable to get a list of queues from the server!")
            queues = {}
        queue = self.args.queue or self._get_queue(queues)
        if queue not in queues.keys():
            print(
                "WARNING: '{}' is not in the list of known "
                "queues".format(queue)
            )
        try:
            images = self.client.get_images(queue)
        except OSError:
            logger.warning("Unable to get a list of images from the server!")
            images = {}
        image = self.args.image or _get_image(images)
        if (
            not image.startswith(("http://", "https://"))
            and image not in images.keys()
        ):
            sys.exit(
                "ERROR: '{}' is not in the list of known "
                "images for that queue, please select "
                "another.".format(image)
            )
        if image.startswith(("http://", "https://")):
            image = "url: " + image
        else:
            image = images[image]
        ssh_keys = self.args.key or _get_ssh_keys()
        for ssh_key in ssh_keys:
            if not ssh_key.startswith("lp:") and not ssh_key.startswith("gh:"):
                sys.exit(
                    "Please enter keys in the form lp:userid or gh:userid"
                )
        template = inspect.cleandoc(
            """job_queue: {queue}
                                    provision_data:
                                        {image}
                                    reserve_data:
                                        ssh_keys:"""
        )
        for ssh_key in ssh_keys:
            template += "\n      - {}".format(ssh_key)
        job_data = template.format(queue=queue, image=image)
        print("\nThe following yaml will be submitted:")
        print(job_data)
        if self.args.dry_run:
            return
        answer = input("Proceed? (Y/n) ")
        if answer in ("Y", "y", ""):
            job_id = self.submit_job_data(job_data)
            print("Job submitted successfully!")
            print("job_id: {}".format(job_id))
            self.do_poll(job_id)

    def _get_queue(self, queues):
        """Ask the user which queue to use from a list"""
        queue = ""
        while not queue or queue == "?":
            queue = input("\nWhich queue do you want to use? ('?' to list) ")
            if not queue:
                continue
            if queue == "?":
                print("\nAdvertised queues on this server:")
                for name, description in sorted(queues.items()):
                    print(" {} - {}".format(name, description))
                queue = self._get_queue(queues)
            if queue not in queues.keys():
                print(
                    "WARNING: '{}' is not in the list of known "
                    "queues".format(queue)
                )
                answer = input("Do you still want to use it? (y/N) ")
                if answer.lower() != "y":
                    queue = ""
        return queue

    def get_latest_output(self, job_id):
        """Get the latest output from a running job

        :param str job_id: Job ID
        :return str: New output from the running job
        """
        output = ""
        try:
            output = self.client.get_output(job_id)
        except client.HTTPError as exc:
            if exc.status == 204:
                # We are still waiting for the job to start
                pass
        return output

    def get_job_state(self, job_id):
        """Return the job state for the specified job_id

        :param str job_id: Job ID
        :raises SystemExit: Exit with HTTP error code
        :return str : Job state
        """
        try:
            return self.client.get_status(job_id)
        except client.HTTPError as exc:
            if exc.status == 204:
                sys.exit(
                    "No data found for that job id. Check the "
                    "job id to be sure it is correct"
                )
            if exc.status == 400:
                sys.exit(
                    "Invalid job id specified. Check the job id "
                    "to be sure it is correct"
                )
            if exc.status == 404:
                sys.exit(
                    "Received 404 error from server. Are you "
                    "sure this is a testflinger server?"
                )
        except (IOError, ValueError) as exc:
            # For other types of network errors, or JSONDecodeError if we got
            # a bad return from get_status()
            logger.debug("Unable to retrieve job state: %s", exc)
        return "unknown"
