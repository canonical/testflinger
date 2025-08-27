# Copyright (C) 2023 Canonical
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

"""Client for talking to Testflinger Server."""

import json
import logging
import urllib.parse

import requests

logger = logging.getLogger(__name__)


class TFClient:
    """Testflinger connection class."""

    def __init__(self, url):
        """Initialize the client with the url of the server.

        :param url: URL of the Testflinger server
        """
        if not url or not url.startswith("http"):
            raise ValueError(
                "Config item testflinger_server URL for multi-device "
                "connectors must be specified and must start with http or "
                "https!"
            )
        self.server = url

    def get(self, uri_frag, timeout=15):
        """Submit a GET request to the server
        :param uri_frag:
            endpoint for the GET request
        :return:
            String containing the response from the server.
        """
        uri = urllib.parse.urljoin(self.server, uri_frag)
        try:
            req = requests.get(uri, timeout=timeout)
        except requests.exceptions.ConnectionError:
            logger.error("Unable to communicate with specified server.")
            raise
        except IOError:
            # This should catch all other timeout cases
            logger.error(
                "Timeout while trying to communicate with the server."
            )
            raise

        try:
            # If anything else went wrong, raise the proper exception
            req.raise_for_status()
        except OSError:
            logger.error(
                "Received status code %s from server.", req.status_code
            )
            raise
        return req.text

    def post(self, uri_frag, data, timeout=15):
        """Submit a POST request to the server
        :param uri_frag:
            endpoint for the POST request
        :return:
            String containing the response from the server.
        """
        uri = urllib.parse.urljoin(self.server, uri_frag)
        try:
            req = requests.post(uri, json=data, timeout=timeout)
        except requests.exceptions.ConnectTimeout:
            logger.error(
                "Timeout while trying to communicate with the server."
            )
            raise
        except requests.exceptions.ConnectionError:
            logger.error("Unable to communicate with specified server.")
            raise

        try:
            # If anything else went wrong, raise the proper exception
            req.raise_for_status()
        except OSError:
            logger.error(
                "Received status code %s from server.", req.status_code
            )
            raise
        return req.text

    def get_status(self, job_id):
        """Get the status of a test job.

        :param job_id:
            ID for the test job
        :return:
            String containing the job_state for the specified job_id
            (waiting, setup, provision, test, reserved, released,
            cancelled, complete)
        """
        try:
            endpoint = f"/v1/result/{job_id}"
            data = json.loads(self.get(endpoint))
            state = data.get("job_state")
        except OSError:
            logger.error("Unable to get status for job %s", job_id)
            state = "unknown"
        return state

    def get_results(self, job_id):
        """Get the results of a test job.

        :param job_id:
            ID for the test job
        :return:
            dict containing the results for the specified job_id
        """
        try:
            endpoint = f"/v1/result/{job_id}"
            data = json.loads(self.get(endpoint))
        except OSError:
            logger.error("Unable to get results for job %s", job_id)
            data = {}
        return data

    def submit_job(self, job_data):
        """Submit a test job to the testflinger server.

        :param job_data:
            dict of data for the job to submit
        :return:
            ID for the test job
        """
        endpoint = "/v1/job"
        response = self.post(endpoint, job_data)
        return json.loads(response).get("job_id")

    def submit_agent_job(self, job_data):
        """Submit a child job to the testflinger server with credential inheritance.

        :param job_data:
            dict of data for the job to submit, must include parent_job_id
        :return:
            ID for the test job
        """
        endpoint = "/v1/agent/jobs"
        response = self.post(endpoint, job_data)
        return json.loads(response).get("job_id")

    def cancel_job(self, job_id):
        """Tell the server to cancel a specified job_id."""
        try:
            self.post(f"/v1/job/{job_id}/action", {"action": "cancel"})
        except requests.exceptions.HTTPError as exc:
            # Ignore it if the job is already cancelled or completed
            if exc.response.status_code != 400:
                raise
        except OSError:
            logger.error("Unable to cancel job %s", job_id)
            raise
