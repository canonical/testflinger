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
import requests
import shutil
import tempfile
import time

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
        user = os.environ.get("INFLUX_USER", "")
        password = os.environ.get("INFLUX_PW", "")
        port = int(os.environ.get("INFLUX_PORT", 8086))
        host = os.environ.get("INFLUX_HOST")
        if not host:
            logger.error("InfluxDB host undefined")
            return

        influx_client = InfluxDBClient(
            host, port, user, password, self.influx_agent_db
        )

        # ensure we can connect to influxdb host
        try:
            influx_client.ping()
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
            job_request = requests.get(
                job_uri, params={"queue": queue_list}, timeout=10
            )
            if job_request.content:
                return job_request.json()
            else:
                return None
        except RequestException as exc:
            logger.error(exc)
            # Wait a little extra before trying again
            time.sleep(60)

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
            job_request = requests.post(result_uri, json=data, timeout=30)
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
            job_request = requests.get(result_uri, timeout=30)
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
        with open(os.path.join(rundir, "testflinger.json")) as f:
            job_data = json.load(f)
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
                    artifact_request = requests.post(
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
            job_request = requests.post(
                output_uri, data=data.encode("utf-8"), timeout=60
            )
        except RequestException as exc:
            logger.error(exc)
            return False
        return bool(job_request)

    def post_queues(self, data):
        """Post the list of advertised queues to testflinger server

        :param data:
            dict of queue name and descriptions to send to the server
        """
        queues_uri = urljoin(self.server, "/v1/agents/queues")
        try:
            requests.post(queues_uri, json=data, timeout=30)
        except RequestException as exc:
            logger.error(exc)

    def post_images(self, data):
        """Post the list of advertised images to testflinger server

        :param data:
            dict of queues containing dicts of imgae names and provision data
        """
        images_uri = urljoin(self.server, "/v1/agents/images")
        try:
            requests.post(images_uri, json=data, timeout=30)
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

    def post_influx(self, job_id, phase, duration, result):
        """Post the relevant data points to testflinger server

        :param data:
            dict of various agent data points to send to the api server
        """
        if not self.influx_client:
            return

        data = [
            {
                "measurement": "phase result",
                "tags": {
                    "agent": self.config.get("agent_id"),
                    "phase": phase,
                    "result": result,
                },
                "fields": {
                    "duration": duration,
                },
                "time": int(time.time()),
            },
        ]

        try:
            self.influx_client.write_points(
                data,
                database=self.influx_agent_db,
                time_precision="s",
                protocol="json",
            )
        except InfluxDBClientError as exc:
            logger.error(exc)
