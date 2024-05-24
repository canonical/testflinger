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

import logging
import json
import os
from pathlib import Path
import requests
import shutil
import tempfile
import time

from typing import List, Dict
from urllib.parse import urljoin
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from requests.exceptions import RequestException, ConnectionError
from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError

from testflinger_agent.errors import TFServerError

logger = logging.getLogger(__name__)


class TestflingerClient:
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
        port = int(os.environ.get("INFLUX_PORT", 8086))
        user = os.environ.get("INFLUX_USER", "")
        password = os.environ.get("INFLUX_PW", "")

        influx_client = InfluxDBClient(
            host, port, user, password, self.influx_agent_db
        )

        # ensure we can connect to influxdb
        try:
            influx_client.create_database(self.influx_agent_db)
        except ConnectionError as exc:
            logger.error(exc)
        else:
            return influx_client

    def check_jobs(self):
        """Check for new jobs for on the Testflinger server

        :return: Dict with job data, or None if no job found
        """
        try:
            job_uri = urljoin(self.server, "/v1/job")
            queue_list = self.config.get("job_queues")
            logger.debug("Requesting a job")
            job_request = self.session.get(
                job_uri, params={"queue": queue_list}, timeout=30
            )
            if job_request.content:
                return job_request.json()
            else:
                return None
        except RequestException as exc:
            logger.error(exc)
            # Wait a little extra before trying again
            time.sleep(60)

    def get_attachments(self, job_id: str, path: Path):
        """Download the attachment archive associated with a job

        :param job_id:
            Id for the job
        :param path:
            Where to save the attachment archive
        """
        uri = urljoin(self.server, f"/v1/job/{job_id}/attachments")
        with requests.get(uri, stream=True, timeout=600) as response:
            if response.status_code != 200:
                logger.error(
                    f"Unable to retrieve attachments for job {job_id} "
                    f"(error: {response.status_code})"
                )
                raise TFServerError(response.status_code)
            with open(path, "wb") as attachments:
                for chunk in response.iter_content(chunk_size=4096):
                    attachments.write(chunk)

    def check_job_state(self, job_id):
        job_data = self.get_result(job_id)
        if job_data:
            return job_data.get("job_state")

    def repost_job(self, job_data):
        """ "Resubmit the job to the testflinger server with the same id

        :param job_id:
            id for the job on which we want to post results
        """
        job_uri = urljoin(self.server, "/v1/job")
        job_id = job_data.get("job_id")
        logger.info("Resubmitting job: %s", job_id)
        job_output = """
            There was an unrecoverable error while running this stage. Your job
            will attempt to be automatically resubmitted back to the queue.
            Resubmitting job: {}\n""".format(
            job_id
        )
        self.post_live_output(job_id, job_output)
        try:
            job_request = self.session.post(job_uri, json=job_data)
        except RequestException as exc:
            logger.error(exc)
            raise TFServerError("other exception") from exc
        if not job_request:
            logger.error(
                "Unable to re-post job to: %s (error: %s)"
                % (job_uri, job_request.status_code)
            )
            raise TFServerError(job_request.status_code)

    def post_job_state(self, job_id, phase):
        """Update the job_state on the testflinger server"""
        try:
            self.post_result(job_id, {"job_state": phase})
        except TFServerError:
            pass

    def post_result(self, job_id, data):
        """Post data to the testflinger server result for this job

        :param job_id:
            id for the job on which we want to post results
        :param data:
            dict with data to be posted in json
        """
        result_uri = urljoin(self.server, "/v1/result/")
        result_uri = urljoin(result_uri, job_id)
        try:
            job_request = self.session.post(result_uri, json=data, timeout=30)
        except RequestException as exc:
            logger.error(exc)
            raise TFServerError("other exception") from exc
        if not job_request:
            logger.error(
                "Unable to post results to: %s (error: %s)"
                % (result_uri, job_request.status_code)
            )
            raise TFServerError(job_request.status_code)

    def get_result(self, job_id):
        """Get current results data to the testflinger server for this job

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
        except RequestException as exc:
            logger.error(exc)
            return {}
        if not job_request:
            logger.error(
                "Unable to get results from: %s (error: %s)"
                % (result_uri, job_request.status_code)
            )
            return {}
        if job_request.content:
            return job_request.json()
        else:
            return {}

    def transmit_job_outcome(self, rundir):
        """Post job outcome json data to the testflinger server

        :param rundir:
            Execution dir where the results can be found
        """
        try:
            with open(os.path.join(rundir, "testflinger.json")) as f:
                job_data = json.load(f)
        except OSError:
            logger.error(
                f"Unable to read job ID from {rundir}/testflinger.json. "
                "This may be a job that was already transmitted, but "
                "couldn't be removed."
            )
            return
        job_id = job_data.get("job_id")
        # If we find an 'artifacts' dir under rundir, archive it, and transmit
        # it to the Testflinger server
        artifacts_dir = os.path.join(rundir, "artifacts")
        if os.path.isdir(artifacts_dir):
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
                    file_upload = {
                        "file": ("file", tarball, "application/x-gzip")
                    }
                    artifact_request = self.session.post(
                        artifact_uri, files=file_upload, timeout=600
                    )
                if not artifact_request:
                    logger.error(
                        "Unable to post results to: %s (error: %s)"
                        % (artifact_uri, artifact_request.status_code)
                    )
                    raise TFServerError(artifact_request.status_code)
                else:
                    shutil.rmtree(artifacts_dir)
        # Do not retransmit outcome if it's already been done and removed
        outcome_file = os.path.join(rundir, "testflinger-outcome.json")
        if os.path.isfile(outcome_file):
            logger.info("Submitting job outcome for job: %s" % job_id)
            with open(outcome_file) as f:
                data = json.load(f)
                data["job_state"] = "complete"
                self.post_result(job_id, data)
            # Remove the outcome file so we don't retransmit
            os.unlink(outcome_file)
        shutil.rmtree(rundir)

    def post_live_output(self, job_id, data):
        """Post output data to the testflinger server for this job

        :param job_id:
            id for the job on which we want to post results
        :param data:
            string with latest output data
        """
        output_uri = urljoin(
            self.server, "/v1/result/{}/output".format(job_id)
        )
        try:
            job_request = self.session.post(
                output_uri, data=data.encode("utf-8"), timeout=60
            )
        except RequestException as exc:
            logger.error(exc)
            return False
        return bool(job_request)

    def post_advertised_queues(self):
        """Post the list of advertised queues to testflinger server"""
        if "advertised_queues" not in self.config:
            return
        queues_uri = urljoin(self.server, "/v1/agents/queues")
        try:
            self.session.post(
                queues_uri, json=self.config["advertised_queues"], timeout=30
            )
        except RequestException as exc:
            logger.error(exc)

    def post_advertised_images(self):
        """Post the list of advertised images to testflinger server"""
        if "advertised_images" not in self.config:
            return
        images_uri = urljoin(self.server, "/v1/agents/images")
        try:
            self.session.post(
                images_uri, json=self.config["advertised_images"], timeout=30
            )
        except RequestException as exc:
            logger.error(exc)

    def post_agent_data(self, data):
        """Post the relevant data points to testflinger server

        :param data:
            dict of various agent data points to send to the api server
        """
        agent_data_uri = urljoin(self.server, "/v1/agents/data/")
        agent_data_url = urljoin(agent_data_uri, self.config.get("agent_id"))
        try:
            self.session.post(agent_data_url, json=data, timeout=30)
        except RequestException as exc:
            logger.error(exc)

    def post_influx(self, phase, result=None):
        """Post the relevant data points to testflinger server

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
        """Post the outcome of provisioning to the server

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
        except RequestException as exc:
            logger.warning("Unable to post provision log to server: %s", exc)

    def post_status_update(
        self, job_queue: str, webhook: str, events: List[Dict[str, str]]
    ):
        """
        Posts status updates about the running job as long as there is a
        webhook

        :param job_queue:
            TestFlinger queue the currently running job belongs to
        :param webhook:
            String URL to post status update to
        :param events:
            List of accumulated test events

        """
        if webhook is None:
            return

        status_update_request = {
            "agent_id": self.config.get("agent_id"),
            "job_queue": job_queue,
            "job_status_webhook": webhook,
            "events": events,
        }
        status_update_uri = urljoin(self.server, "/v1/agents/status")
        try:
            job_request = self.session.post(
                status_update_uri, json=status_update_request, timeout=30
            )
        except RequestException as exc:
            logger.error("Server Error: %s" % exc)
            job_request = None
        if not job_request:
            logger.error(
                "Unable to post status updates to: %s (error: %s)"
                % (status_update_uri, job_request.status_code)
            )
