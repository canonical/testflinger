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

"""Testflinger client module."""

import base64
import json
import logging
import sys
import time
import urllib.parse
from http import HTTPStatus
from pathlib import Path

import requests

from testflinger_cli.enums import LogType, TestPhase
from testflinger_cli.errors import VPNError

logger = logging.getLogger(__name__)

# Maximum backoff delay in seconds
MAX_BACKOFF_TIME = 60


class HTTPError(Exception):
    """Exception class for HTTP error codes."""

    def __init__(self, status, msg=""):
        super().__init__(status)
        self.status = status
        self.msg = msg


class Client:
    """Testflinger connection client."""

    def __init__(self, server, error_threshold=3):
        self.server = server
        self.error_count = 0
        self.error_threshold = error_threshold

    def _handle_response_error(self, req: requests.Request):
        """Handle non-OK response status codes.

        :param req: The response object
        :raises HTTPError: Exception with status code and error message
        """
        try:
            error_json = req.json()
        except ValueError as exc:
            # If server sent 403 without JSON object, this means that request
            # was aborted by a VPN issue rather than an actual server response
            if req.status_code == HTTPStatus.FORBIDDEN:
                raise VPNError from exc

            # Raise HTTPError with clear text message if any other ValueError
            raise HTTPError(status=req.status_code, msg=req.text) from exc

        # flask `abort` returns a JSON object with error message
        error_message = error_json.get("message", req.text)
        # For schema validation errors, try to get detailed error info
        if req.status_code == HTTPStatus.UNPROCESSABLE_ENTITY and (
            validation_errors := error_json.get("detail", {}).get("json", {})
        ):
            error_details = ", ".join(
                f"{field}: {msg}" for field, msg in validation_errors.items()
            )
            error_message = f"{error_message} - {error_details}"

        raise HTTPError(status=req.status_code, msg=error_message)

    def get(
        self, uri_frag: str, timeout: int = 15, headers: dict | None = None
    ):
        """Submit a GET request to the server.

        :param uri_frag: endpoint for the GET request
        :param timeout: timeout for the request to complete
        :param headers: authentication header if needed to perfom request
        :return: string containing the response from the server
        """
        uri = urllib.parse.urljoin(self.server, uri_frag)
        try:
            req = requests.get(uri, timeout=timeout, headers=headers)
            self.error_count = 0
        except (IOError, requests.exceptions.ConnectionError) as exc:
            self.error_count += 1
            if self.error_count % self.error_threshold == 0:
                logger.warning(
                    "Error communicating with the server for the past %s "
                    "requests, but will continue to retry. Last error: %s",
                    self.error_count,
                    exc,
                )
            # Exponential backoff before re-raising exception
            backoff_delay = min(2**self.error_count, MAX_BACKOFF_TIME)
            time.sleep(backoff_delay)
            raise
        # If request was not successful, raise HTTPError with parsed response
        if req.status_code != HTTPStatus.OK:
            self._handle_response_error(req)
        return req.text

    def post(
        self,
        uri_frag: str,
        data: dict,
        timeout: int = 15,
        headers: dict | None = None,
    ):
        """Submit a POST request to the server.

        :param uri_frag: endpoint for the POST request
        :param data: JSON data to send in the request body
        :param timeout: timeout for the request to complete
        :param headers: authentication header if needed to perfom request
        :return: string containing the response from the server
        """
        uri = urllib.parse.urljoin(self.server, uri_frag)
        try:
            req = requests.post(
                uri, json=data, timeout=timeout, headers=headers
            )
        except requests.exceptions.ConnectTimeout:
            logger.error(
                "Timeout while trying to communicate with the server."
            )
            sys.exit(1)
        except requests.exceptions.ConnectionError:
            logger.error("Unable to communicate with specified server.")
            sys.exit(1)
        # If request was not successful, raise HTTPError with parsed response
        if req.status_code != HTTPStatus.OK:
            self._handle_response_error(req)
        return req.text

    def put(
        self,
        uri_frag: str,
        data: dict,
        timeout: int = 15,
        headers: dict | None = None,
    ):
        """Submit a PUT request to the server.

        :param uri_frag: endpoint for the PUT request
        :param data: JSON data to send in the request body
        :param timeout: timeout for the request to complete
        :param headers: authentication header if needed to perfom request
        :return: string containing the response from the server
        """
        uri = urllib.parse.urljoin(self.server, uri_frag)
        try:
            req = requests.put(
                uri, json=data, timeout=timeout, headers=headers
            )
        except requests.exceptions.ConnectTimeout:
            logger.error(
                "Timeout while trying to communicate with the server."
            )
            sys.exit(1)
        except requests.exceptions.ConnectionError:
            logger.error("Unable to communicate with specified server.")
            sys.exit(1)
        # If request was not successful, raise HTTPError with parsed response
        if req.status_code != HTTPStatus.OK:
            self._handle_response_error(req)
        return req.text

    def delete(
        self, uri_frag: str, timeout: int = 15, headers: dict | None = None
    ):
        """Submit a DELETE request to the server
        :param uri_frag: endpoint for the DELETE request
        :param timeout: timeout for the request to complete
        :param headers: authentication header if needed to perfom request.
        :return: string containing the response from the server.
        """
        uri = urllib.parse.urljoin(self.server, uri_frag)
        try:
            req = requests.delete(uri, timeout=timeout, headers=headers)
        except requests.exceptions.ConnectTimeout:
            logger.error(
                "Timeout while trying to communicate with the server."
            )
            sys.exit(1)
        except requests.exceptions.ConnectionError:
            logger.error("Unable to communicate with specified server.")
            sys.exit(1)
        # If request was not successful, raise HTTPError with parsed response
        if req.status_code != HTTPStatus.OK:
            self._handle_response_error(req)
        return req.text

    def put_file(self, uri_frag: str, path: Path, timeout: float):
        """Stream a file to the server using a POST request.

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
                files = {"file": (path.name, file, "application/x-gzip")}
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
                logger.error("A connection error occured %s", error)
                raise
            response.raise_for_status()

    def get_status(self, job_id: str) -> dict:
        """Get the status of a test job.

        :param job_id: ID for the test job
        :return: data containing the job state and each test phase status
        """
        endpoint = "/v1/result/{}".format(job_id)
        data = json.loads(self.get(endpoint))
        job_status = {
            phase.value: data.get(f"{phase.value}_status")
            for phase in TestPhase
        }
        job_status["job_state"] = data.get("job_state")
        return job_status

    def get_agent_data(self, agent_name: str) -> dict:
        """Get all the data for a specified agent.

        :param agent_name: Name of the agent to retrieve its data
        :return: Dict containing all the data from the agent.
        """
        endpoint = f"/v1/agents/data/{agent_name}"
        return json.loads(self.get(endpoint))

    def get_agent_status_by_queue(self, queue: str) -> list[dict]:
        """Get the status of the agents by a specified queue.

        :param queue: Name of the queue to retrieve its agent status
        :return: Dict with the name and status for each agent in queue.
        """
        endpoint = f"/v1/queues/{queue}/agents"
        data = json.loads(self.get(endpoint))

        agents_status = [
            {"name": agent["name"], "status": agent["state"]} for agent in data
        ]
        return agents_status

    def post_job_state(self, job_id, state):
        """Post the status of a test job.

        :param job_id:
            ID for the test job
        :param state:
            Job state to set for the specified job
        """
        endpoint = "/v1/result/{}".format(job_id)
        data = {"job_state": state}
        self.post(endpoint, data)

    def submit_job(self, data: dict, headers: dict = None) -> str:
        """Submit a test job to the testflinger server.

        :param job_data:
            Dictionary containing data for the job to submit
        :return:
            ID for the test job
        """
        endpoint = "/v1/job"
        response = self.post(endpoint, data, headers=headers)
        return json.loads(response).get("job_id")

    def authenticate(self, client_id: str, secret_key: str) -> dict:
        """Authenticate client id and secret key with the server
        and returns access and refresh tokens.

        :param client_id: user used for authentication
        :param secret_key: secret used to authenticate user
        :return: access_token, token_type, expiration and refresh token
        """
        endpoint = "/v1/oauth2/token"
        id_key_pair = f"{client_id}:{secret_key}"
        encoded_id_key_pair = base64.b64encode(
            id_key_pair.encode("utf-8")
        ).decode("utf-8")
        headers = {"Authorization": f"Basic {encoded_id_key_pair}"}
        response = self.post(endpoint, {}, headers=headers)
        return json.loads(response)

    def refresh_authentication(self, refresh_token: str) -> dict:
        """Refresh access_token by using stored refresh_token.

        :param refresh_token: Opaque token used for refreshing access_token
        :return: access_token with token type and expiration
        """
        endpoint = "/v1/oauth2/refresh"
        response = self.post(endpoint, data={"refresh_token": refresh_token})
        return json.loads(response)

    def post_attachment(self, job_id: str, path: Path, timeout: int):
        """Send a test job attachment to the testflinger server.

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
        """Show the JSON job definition for the specified ID.

        :param job_id:
            ID for the test job
        :return:
            JSON job definition for the specified ID
        """
        endpoint = "/v1/job/{}".format(job_id)
        return json.loads(self.get(endpoint))

    def get_results(self, job_id):
        """Get results for a specified test job.

        :param job_id:
            ID for the test job
        :return:
            Dict containing the results returned from the server
        """
        endpoint = "/v1/result/{}".format(job_id)
        return json.loads(self.get(endpoint))

    def get_artifact(self, job_id, path: Path):
        """Get results for a specified test job.

        :param job_id:
            ID for the test job
        :param path:
            Path and filename for the artifact file
        """
        endpoint = "/v1/result/{}/artifact".format(job_id)
        uri = urllib.parse.urljoin(self.server, endpoint)
        req = requests.get(uri, timeout=15, stream=True)
        if req.status_code != HTTPStatus.OK:
            raise HTTPError(req.status_code)
        with path.open("wb") as artifact:
            for chunk in req.raw.stream(4096, decode_content=False):
                if chunk:
                    artifact.write(chunk)

    def get_logs(
        self,
        job_id: str,
        log_type: LogType,
        phase: TestPhase,
        start_fragment: int,
        start_timestamp: str,
    ) -> dict:
        """Get the latest output/serial output for a specified test job.

        :param job_id: ID for the test job
        :param log_type: Enum representing normal output or serial output
        :param phase: Phase to retrieve logs for
        :param start_fragment: First log fragment to start from
        :param start_timestamp: Timestamp to start retrieving logs from
        :return: Combined log fragments and latest fragment number.
        """
        endpoint = f"/v1/result/{job_id}/log/{log_type.value}"
        params = {"start_fragment": start_fragment}
        if start_timestamp is not None:
            params["start_timestamp"] = start_timestamp.isoformat()
        if phase is not None:
            params["phase"] = phase
        encoded_params = urllib.parse.urlencode(params)
        complete_url_frag = f"{endpoint}?{encoded_params}"
        return json.loads(self.get(complete_url_frag))

    def get_job_position(self, job_id):
        """Get the status of a test job.

        :param job_id:
            ID for the test job
        :return:
            String containing the queue position for the specified ID
            i.e. how many jobs are ahead of it in the queue
        """
        endpoint = "/v1/job/{}/position".format(job_id)
        return self.get(endpoint)

    def get_queues(self):
        """Get the advertised queues from the testflinger server."""
        endpoint = "/v1/agents/queues"
        data = self.get(endpoint)
        try:
            return json.loads(data)
        except ValueError:
            return {}

    def get_images(self, queue):
        """Get the advertised images from the testflinger server."""
        endpoint = f"/v1/agents/images/{queue}"
        data = self.get(endpoint)
        try:
            return json.loads(data)
        except ValueError:
            return {}

    def get_agents_on_queue(self, queue):
        """Get the list of all agents listening to a specified queue."""
        endpoint = f"/v1/queues/{queue}/agents"
        data = self.get(endpoint)
        return json.loads(data)

    def get_jobs_on_queue(self, queue: str) -> dict:
        """Get the list of jobs assigned to a queue.

        :param queue: String with the queue name where to list the jobs
        """
        endpoint = f"/v1/queues/{queue}/jobs"
        data = self.get(endpoint)
        return json.loads(data)

    def set_agent_status(self, agent: str, status: str, comment: str) -> None:
        """Modify the status of an agent based on user request.

        :param agent: Name of the agent
        :param status: Status to send to the agent
        :param comment: Reason for changing the status
        """
        endpoint = f"/v1/agents/data/{agent}"
        data = {"state": status, "comment": comment}
        self.post(endpoint, data)

    def set_client_permissions(self, auth_header: dict, json_data: dict):
        """Set existing client_id permissions.

        :param auth_header: Auth header required to perform PUT request
        :param json_data: JSON with updated client permissions
        """
        client_id = json_data.pop("client_id")
        endpoint = f"/v1/client-permissions/{client_id}"
        return self.put(endpoint, data=json_data, headers=auth_header)

    def get_client_permissions(
        self, auth_header: dict, tf_client_id: str | None = None
    ) -> list[dict] | None:
        """Get the permissions from specified client.

        If no client specified, will provide all client permissions.

        :param auth_header: Auth header required to perform GET request
        :param tf_client_id: Specified client to retrieve permissions from
        """
        if tf_client_id:
            endpoint = f"/v1/client-permissions/{tf_client_id}"
        else:
            endpoint = "/v1/client-permissions"
        return json.loads(self.get(endpoint, headers=auth_header))

    def delete_client_permissions(
        self, auth_header: dict, tf_client_id: str
    ) -> None:
        """Delete a client_id along with its permissions.

        :param auth_header: Auth header required to perform DELETE request
        :param tf_client_id: Specified client to delete permissions from
        """
        endpoint = f"/v1/client-permissions/{tf_client_id}"
        self.delete(endpoint, headers=auth_header)
