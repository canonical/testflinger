# Copyright (C) 2016-2022 Canonical
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import json
import logging
import os
import shutil
import tempfile
import time
from dataclasses import asdict, dataclass
from http import HTTPStatus
from pathlib import Path
from typing import Dict, List
from urllib.parse import urljoin

import requests
from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError
from requests import HTTPError
from requests.adapters import HTTPAdapter
from testflinger_common.enums import LogType
from urllib3.util import Retry

from testflinger_agent.errors import TFServerError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LogEndpointInput:
    """Schema for Testflinger Log endpoints."""

    fragment_number: int
    timestamp: str
    phase: str
    log_data: str


class TestflingerClient:
    __test__ = False
    """This prevents pytest from trying to run this class as a test."""

    def __init__(self, config):
        self.config = config
        self.server = self.config.get(
            "server_address", "https://testflinger.canonical.com"
        )
        if not self.server.lower().startswith("http"):
            self.server = "http://" + self.server
        self.session = self._requests_retry(retries=5)
        self.influx_agent_db = "agent_jobs"
        self.influx_client = self._configure_influx()

    def _requests_retry(self, retries=3):
        session = requests.Session()
        retry = Retry(
            total=retries,
            read=retries,
            connect=retries,
            backoff_factor=0.3,
            status_forcelist=(500, 502, 503, 504),
            allowed_methods=False,  # allow retry on all methods
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _configure_influx(self):
        """Configure InfluxDB client using environment variables.

        :return: influxdb object or None
        """
        host = os.environ.get("INFLUX_HOST")
        if not host:
            logger.error("InfluxDB host undefined")
            return None
        port = int(os.environ.get("INFLUX_PORT", "8086"))
        user = os.environ.get("INFLUX_USER", "")
        password = os.environ.get("INFLUX_PW", "")

        influx_client = InfluxDBClient(
            host, port, user, password, self.influx_agent_db
        )

        # ensure we can connect to influxdb
        try:
            influx_client.create_database(self.influx_agent_db)
        except requests.exceptions.ConnectionError as exc:
            logger.error(exc)
        else:
            return influx_client

    def check_jobs(self):
        """Check for new jobs for on the Testflinger server.

        If the agent has restricted queues, only accept jobs from those queues.

        :return: Dict with job data, or None if no job found
        """
        agent_id = self.config.get("agent_id")
        agent_data = self.get_agent_data(agent_id)

        all_queues = self.config.get("job_queues", [])
        restricted_to = agent_data.get("restricted_to", {})
        restricted_queues = [
            queue for queue, owners in restricted_to.items() if owners
        ]

        queue_list = restricted_queues or all_queues

        job_uri = urljoin(self.server, "/v1/job")
        logger.debug("Requesting a job")
        try:
            job_request = self.session.get(
                job_uri, params={"queue": queue_list}, timeout=30
            )
            job_request.raise_for_status()
        except HTTPError as exc:
            if exc.response.status_code == HTTPStatus.UNAUTHORIZED:
                # Re-register the agent to authenticate it.
                self.post_agent_data({"job_id": ""})
                return None
            logger.error(exc)
        except requests.exceptions.RequestException as exc:
            logger.error(exc)
            # Wait a little extra before trying again
            time.sleep(60)
        else:
            if job_request.content:
                return job_request.json()
            return None

    def get_attachments(self, job_id: str, path: Path):
        """Download the attachment archive associated with a job.

        :param job_id:
            Id for the job
        :param path:
            Where to save the attachment archive
        """
        uri = urljoin(self.server, f"/v1/job/{job_id}/attachments")
        with requests.get(uri, stream=True, timeout=600) as response:
            if not response:
                logger.error(
                    "Unable to retrieve attachments for job: %s (error: %d)",
                    job_id,
                    response.status_code,
                )
                raise TFServerError(response.status_code)
            with open(path, "wb") as attachments:
                for chunk in response.iter_content(chunk_size=4096):
                    attachments.write(chunk)

    def check_job_state(self, job_id):
        job_data = self.get_result(job_id)
        if job_data:
            return job_data.get("job_state")

    def post_job_state(self, job_id, phase):
        """Update the job_state on the testflinger server."""
        try:
            self.post_result(job_id, {"job_state": phase})
        except TFServerError:
            pass

    def post_result(self, job_id, data):
        """Post data to the testflinger server result for this job.

        :param job_id:
            id for the job on which we want to post results
        :param data:
            dict with data to be posted in json
        """
        result_uri = urljoin(self.server, "/v1/result/")
        result_uri = urljoin(result_uri, job_id)
        try:
            job_request = self.session.post(result_uri, json=data, timeout=30)
        except requests.exceptions.RequestException as exc:
            logger.error(exc)
            raise TFServerError("other exception") from exc
        if not job_request:
            logger.error(
                "Unable to post results to: %s (error: %d)",
                result_uri,
                job_request.status_code,
            )
            raise TFServerError(job_request.status_code)

    def get_result(self, job_id):
        """Get current results data to the testflinger server for this job.

        :param job_id:
            id for the job on which we want to post results
        :param data:
            dict with data to be posted in json or an empty dict if
            there was an error
        """
        result_uri = urljoin(self.server, "/v1/result/")
        result_uri = urljoin(result_uri, job_id)
        try:
            job_request = self.session.get(result_uri, timeout=30)
        except requests.exceptions.RequestException as exc:
            logger.error(exc)
            return {}
        if not job_request:
            logger.error(
                "Unable to get results from: %s (error: %d)",
                result_uri,
                job_request.status_code,
            )
            return {}
        if job_request.content:
            return job_request.json()
        else:
            return {}

    def get_agent_data(self, agent_id: str) -> dict:
        """Fetch data for the given agent."""
        url = urljoin(self.server, f"/v1/agents/data/{agent_id}")
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        except (requests.exceptions.RequestException, ValueError) as exc:
            logger.error("Failed to retrieve agent data: %s", exc)
            return {}

    def transmit_job_outcome(self, rundir):
        """Post job outcome json data to the testflinger server.

        :param rundir:
            Execution dir where the results can be found
        """
        try:
            with open(os.path.join(rundir, "testflinger.json")) as f:
                job_data = json.load(f)
        except OSError:
            logger.error(
                "Unable to read job ID from %s/testflinger.json. "
                "This may be a job that was already transmitted, but "
                "couldn't be removed.",
                rundir,
            )
            return
        job_id = job_data.get("job_id")

        try:
            self.save_artifacts(rundir, job_id)
        except OSError:
            # This is usually due to disk full, save what we can and report
            # as much detail as we can for further investigation
            logger.exception("Unable to save artifacts")

        # Do not retransmit outcome if it's already been done and removed
        outcome_file = Path(rundir) / "testflinger-outcome.json"
        if outcome_file.is_file():
            logger.info("Submitting job outcome for job: %s", job_id)
            with outcome_file.open() as f:
                data = json.load(f)
                # Only include status in posted results
                # TODO: Remove pop once backward compatibility is not needed
                data.pop("output", None)
                data.pop("serial", None)
                data["job_state"] = "complete"
                self.post_result(job_id, data)
            # Remove the outcome file so we don't retransmit
            outcome_file.unlink()
        shutil.rmtree(rundir)

    def save_artifacts(self, rundir, job_id):
        """Save artifacts to the testflinger server.

        :param rundir:
            Execution dir where the results can be found
        :param job_id:
            id for the job
        """
        artifacts_dir = os.path.join(rundir, "artifacts")
        if not os.path.isdir(artifacts_dir):
            return

        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_file = os.path.join(tmpdir, "artifacts")
            shutil.make_archive(
                artifact_file,
                format="gztar",
                root_dir=rundir,
                base_dir="artifacts",
            )
            # Create uri for API: /v1/result/<job_id>
            artifact_uri = urljoin(
                self.server, "/v1/result/{}/artifact".format(job_id)
            )
            with open(artifact_file + ".tar.gz", "rb") as tarball:
                file_upload = {"file": ("file", tarball, "application/x-gzip")}
                artifact_request = self.session.post(
                    artifact_uri, files=file_upload, timeout=600
                )
            if not artifact_request:
                logger.error(
                    "Unable to post results to: %s (error: %d)",
                    artifact_uri,
                    artifact_request.status_code,
                )
                raise TFServerError(artifact_request.status_code)
            else:
                shutil.rmtree(artifacts_dir)

    def post_log(
        self,
        job_id: str,
        log_input: LogEndpointInput,
        log_type: LogType,
    ):
        """Post log data to the testflinger server for this job.

        :param job_id: id for the job
        :param log_input: Dataclass with all of the keys for the log endpoint
        :param log_type: Enum of different log types the server accepts
        """
        endpoint = urljoin(self.server, f"/v1/result/{job_id}/log/{log_type}")

        # Define request success flags
        request = None

        # TODO: Remove legacy endpoint support in future versions
        # Define legacy_request success flag
        legacy_request = None

        # Enum is "serial", for compatibility, define "serial_output" instead
        suffix = (
            "serial_output"
            if log_type == LogType.SERIAL_OUTPUT
            else log_type.value
        )
        legacy_endpoint = urljoin(self.server, f"/v1/result/{job_id}/{suffix}")
        # Prioritize writing to legacy endpoint
        try:
            legacy_request = self.session.post(
                legacy_endpoint,
                data=log_input.log_data.encode("utf-8"),
                timeout=60,
            )
        except requests.exceptions.RequestException as exc:
            logger.error(exc)
            logger.info("Fallback to new log endpoint")

        # Write logs to new endpoint
        try:
            request = self.session.post(
                endpoint, json=asdict(log_input), timeout=60
            )
        except requests.exceptions.RequestException as exc:
            logger.error(exc)

        # Return True if either request was successful
        return any(
            req is not None and req.ok for req in (legacy_request, request)
        )

    def post_advertised_queues(self):
        """Post the list of advertised queues to testflinger server."""
        if "advertised_queues" not in self.config:
            return
        queues_uri = urljoin(self.server, "/v1/agents/queues")
        try:
            self.session.post(
                queues_uri, json=self.config["advertised_queues"], timeout=30
            )
        except requests.exceptions.RequestException as exc:
            logger.error(exc)

    def post_advertised_images(self):
        """Post the list of advertised images to testflinger server."""
        if "advertised_images" not in self.config:
            return
        images_uri = urljoin(self.server, "/v1/agents/images")
        try:
            self.session.post(
                images_uri, json=self.config["advertised_images"], timeout=30
            )
        except requests.exceptions.RequestException as exc:
            logger.error(exc)

    def post_agent_data(self, data):
        """Post the relevant data points to testflinger server.

        :param data:
            dict of various agent data points to send to the api server
        """
        agent_data_uri = urljoin(self.server, "/v1/agents/data/")
        agent_data_url = urljoin(agent_data_uri, self.config.get("agent_id"))
        try:
            self.session.post(agent_data_url, json=data, timeout=30)
        except requests.exceptions.RequestException as exc:
            logger.error(exc)

    def post_influx(self, phase, result=None):
        """Post the relevant data points to testflinger server.

        :param data:
            dict of various agent data points to send to the api server
        """
        if not self.influx_client:
            return

        fields = {"phase": phase}

        if result is not None:
            fields["result"] = result

        data = [
            {
                "measurement": "phase result",
                "tags": {
                    "agent": self.config.get("agent_id"),
                },
                "fields": fields,
                "time": time.time_ns(),
            }
        ]

        try:
            self.influx_client.write_points(
                data,
                database=self.influx_agent_db,
                protocol="json",
            )
        except InfluxDBClientError as exc:
            logger.error(exc)

    def post_provision_log(self, job_id: str, exit_code: int, detail: str):
        """Post the outcome of provisioning to the server.

        :param job_id:
            job_id of the job that was running
        :param exitcode:
            exit code from the provision phase
        :param detail:
            string with any known details of the failure
        """
        data = {
            "job_id": job_id,
            "exit_code": exit_code,
            "detail": detail,
        }
        agent_data_uri = urljoin(self.server, "/v1/agents/provision_logs/")
        agent_data_url = urljoin(agent_data_uri, self.config.get("agent_id"))
        try:
            self.session.post(agent_data_url, json=data, timeout=30)
        except requests.exceptions.RequestException as exc:
            logger.warning("Unable to post provision log to server: %s", exc)

    def post_status_update(
        self,
        job_queue: str,
        webhook: str,
        events: List[Dict[str, str]],
        job_id: str,
    ):
        """
        Post status updates about the running job as long as there is a
        webhook.

        :param job_queue:
            TestFlinger queue the currently running job belongs to
        :param webhook:
            String URL to post status update to
        :param events:
            List of accumulated test events
        :param job_id:
            id for the job on which we want to post results

        """
        if webhook is None:
            return

        status_update_request = {
            "agent_id": self.config.get("agent_id"),
            "job_queue": job_queue,
            "job_status_webhook": webhook,
            "events": events,
        }
        status_update_uri = urljoin(self.server, f"/v1/job/{job_id}/events")
        try:
            job_request = self.session.post(
                status_update_uri, json=status_update_request, timeout=30
            )
            # Response code is greater than 399
            if not job_request:
                logger.error(
                    "Unable to post status updates to: %s (error: %d)",
                    status_update_uri,
                    job_request.status_code,
                )
        except requests.exceptions.RequestException as exc:
            logger.error(
                "Unable to post status updates to: %s (error: %s)",
                status_update_uri,
                exc,
            )

    def is_server_reachable(self, timeout=10) -> bool:
        """Check if server is reachable by doing a health check.

        :param timeout: timeout for completing HTTP request
        :returns: True if server is reachable, False otherwise
        """
        try:
            health_url = urljoin(self.server, "/v1")
            response = self.session.get(health_url, timeout=timeout)
            # Mark to False if found any server-side issues
            return response.status_code < 500
        except requests.exceptions.RequestException:
            logger.error("Server connectivity lost")
            return False

    def wait_for_server_connectivity(
        self, interval=30, max_interval=180
    ) -> None:
        """Wait for connection to tf server to continue agent process.

        :param interval: Initial interval between checks
        :param max_interval: Max time to wait between checks
        """
        retry_count = 0
        while True:
            if self.is_server_reachable():
                break
            logger.warning(
                "Testflinger server unreachable, waiting for connectivity"
            )
            time.sleep(interval)
            # Exponentially increase interval between rechecks
            interval = min(interval * (2**retry_count), max_interval)
            retry_count += 1
