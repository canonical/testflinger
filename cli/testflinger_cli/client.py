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
Testflinger client module
"""

import json
import logging
from pathlib import Path
import sys
import urllib.parse

import requests


logger = logging.getLogger(__name__)


class HTTPError(Exception):
    """Exception class for HTTP error codes"""

    def __init__(self, status):
        super().__init__(status)
        self.status = status


class Client:
    """Testflinger connection client"""

    def __init__(self, server):
        self.server = server

    def get(self, uri_frag, timeout=15):
        """Submit a GET request to the server
        :param uri_frag:
            endpoint for the GET request
        :return:
            String containing the response from the server
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
        if req.status_code != 200:
            raise HTTPError(req.status_code)
        return req.text

    def put(self, uri_frag, data, timeout=15):
        """Submit a POST request to the server
        :param uri_frag:
            endpoint for the POST request
        :return:
            String containing the response from the server
        """
        uri = urllib.parse.urljoin(self.server, uri_frag)
        try:
            req = requests.post(uri, json=data, timeout=timeout)
        except requests.exceptions.ConnectTimeout:
            logger.error(
                "Timeout while trying to communicate with the server."
            )
            sys.exit(1)
        except requests.exceptions.ConnectionError:
            logger.error("Unable to communicate with specified server.")
            sys.exit(1)
        if req.status_code != 200:
            raise HTTPError(req.status_code)
        return req.text

    def put_file(self, uri_frag: str, path: Path, timeout: float):
        """Stream a file to the server using a POST request

        :param uri_frag:
            endpoint for the POST request
        :param path:
            the file to be uploaded
        :return:
            String containing the response from the server
        """
        uri = urllib.parse.urljoin(self.server, uri_frag)
        with open(path, "rb") as file:
            try:
                files = {"file": (path.name, file)}
                response = requests.post(uri, files=files, timeout=timeout)
            except requests.exceptions.ConnectTimeout:
                logger.error(
                    "Timeout while trying to connect to the remote server"
                )
                raise
            except requests.exceptions.ReadTimeout:
                logger.error(
                    "Connection established but the server did not send data "
                    "in the alloted amount of time"
                )
                raise
            except requests.exceptions.ConnectionError as error:
                logger.error(f"A connection error occured {error}")
                raise
            response.raise_for_status()

    def get_status(self, job_id):
        """Get the status of a test job

        :param job_id:
            ID for the test job
        :return:
            String containing the job_state for the specified ID
            (waiting, setup, provision, test, reserved, released,
             cancelled, completed)
        """
        endpoint = "/v1/result/{}".format(job_id)
        data = json.loads(self.get(endpoint))
        return data.get("job_state")

    def post_job_state(self, job_id, state):
        """Post the status of a test job

        :param job_id:
            ID for the test job
        :param state:
            Job state to set for the specified job
        """
        endpoint = "/v1/result/{}".format(job_id)
        data = {"job_state": state}
        self.put(endpoint, data)

    def submit_job(self, data: dict) -> str:
        """Submit a test job to the testflinger server

        :param job_data:
            Dictionary containing data for the job to submit
        :return:
            ID for the test job
        """
        endpoint = "/v1/job"
        response = self.put(endpoint, data)
        return json.loads(response).get("job_id")

    def post_attachment(self, job_id: str, path: Path, timeout: int):
        """Send a test job attachment to the testflinger server

        :param job_id:
            ID for the test job
        :param path:
            The path to the attachment to be sent to the server
        :return:
            ID for the test job
        """
        endpoint = f"/v1/job/{job_id}/attachments"
        self.put_file(endpoint, path, timeout=timeout)

    def show_job(self, job_id):
        """Show the JSON job definition for the specified ID

        :param job_id:
            ID for the test job
        :return:
            JSON job definition for the specified ID
        """
        endpoint = "/v1/job/{}".format(job_id)
        return json.loads(self.get(endpoint))

    def get_results(self, job_id):
        """Get results for a specified test job

        :param job_id:
            ID for the test job
        :return:
            Dict containing the results returned from the server
        """
        endpoint = "/v1/result/{}".format(job_id)
        return json.loads(self.get(endpoint))

    def get_artifact(self, job_id, path):
        """Get results for a specified test job

        :param job_id:
            ID for the test job
        :param path:
            Path and filename for the artifact file
        """
        endpoint = "/v1/result/{}/artifact".format(job_id)
        uri = urllib.parse.urljoin(self.server, endpoint)
        req = requests.get(uri, timeout=15, stream=True)
        if req.status_code != 200:
            raise HTTPError(req.status_code)
        with open(path, "wb") as artifact:
            for chunk in req.raw.stream(4096, decode_content=False):
                if chunk:
                    artifact.write(chunk)

    def get_output(self, job_id):
        """Get the latest output for a specified test job

        :param job_id:
            ID for the test job
        :return:
            String containing the latest output from the job
        """
        endpoint = "/v1/result/{}/output".format(job_id)
        return self.get(endpoint)

    def get_job_position(self, job_id):
        """Get the status of a test job

        :param job_id:
            ID for the test job
        :return:
            String containing the queue position for the specified ID
            i.e. how many jobs are ahead of it in the queue
        """
        endpoint = "/v1/job/{}/position".format(job_id)
        return self.get(endpoint)

    def get_queues(self):
        """Get the advertised queues from the testflinger server"""
        endpoint = "/v1/agents/queues"
        data = self.get(endpoint)
        try:
            return json.loads(data)
        except ValueError:
            return {}

    def get_images(self, queue):
        """Get the advertised images from the testflinger server"""
        endpoint = "/v1/agents/images/" + queue
        data = self.get(endpoint)
        try:
            return json.loads(data)
        except ValueError:
            return {}
