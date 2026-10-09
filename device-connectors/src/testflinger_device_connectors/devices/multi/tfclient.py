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

import base64
import json
import logging
import urllib.parse
from functools import cached_property
from http import HTTPStatus

import requests
from requests.auth import AuthBase

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 15


class ClientAuth(AuthBase):
    """Attaches a Bearer token to every request."""

    def __init__(self, client: "TFClient") -> None:
        """Initialize with a TFClient instance.

        :param client: Instance of the client to retrieve access token from
        """
        self.client = client

    def __call__(
        self, req: requests.PreparedRequest
    ) -> requests.PreparedRequest:
        """Attach the current access token to the request.

        :param req: The prepared request object to modify
        :return: The modified request object with Authorization header
        """
        if access_token := self.client.access_token:
            req.headers["Authorization"] = f"Bearer {access_token}"
        return req


class TFClient:
    """Testflinger connection class."""

    def __init__(
        self,
        url: str,
        client_id: str | None = None,
        secret_key: str | None = None,
    ):
        """Initialize the client with the url of the server.

        :param url: URL of the Testflinger server
        :param client_id: Client ID for authenticating with the server.
            If None, requests are sent without authentication.
        :param secret_key: Secret key for authenticating with the server.
            If None, requests are sent without authentication.
        """
        if not url or not url.startswith("http"):
            raise ValueError(
                "Config item testflinger_server URL for multi-device "
                "connectors must be specified and must start with http or "
                "https!"
            )
        self.server = url
        self.client_id = client_id
        self.secret_key = secret_key

    @cached_property
    def access_token(self) -> str | None:
        """Obtain an access token from the server using stored credentials.

        Exchanges the client_id and secret_key for a short-lived access token
        via POST /v1/oauth2/token and caches the result for the lifetime of
        this process. Returns None when no credentials are configured so
        that unauthenticated operation is preserved for environments that
        do not require auth.

        :return: Access token string if successful, None otherwise
        """
        if not self.client_id or not self.secret_key:
            return None

        token_url = urllib.parse.urljoin(self.server, "/v1/oauth2/token")
        id_key_pair = f"{self.client_id}:{self.secret_key}"
        encoded_credentials = base64.b64encode(
            id_key_pair.encode("utf-8")
        ).decode("utf-8")

        try:
            response = requests.post(
                token_url,
                headers={"Authorization": f"Basic {encoded_credentials}"},
                timeout=DEFAULT_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            logger.error("Failed to obtain access token: %s", exc)
            return None

        return response.json().get("access_token")

    def _handle_token_refresh(
        self, response: requests.Response, **kwargs
    ) -> requests.Response:
        """Re-acquire the access token and replay the request on a 401.

        When the server signals token expiry with a 401, this hook
        invalidates the cached token, fetches a fresh one, and replays
        the original exactly once.

        :param response: The response object from the request
        :return: The replayed response on token expiry, otherwise the original
        """
        if response.status_code == HTTPStatus.UNAUTHORIZED:
            if getattr(response.request, "_auth_retry", False):
                return response

            # Consume the response body to return the active connection to
            # the pool for reuse
            _ = response.content

            del self.access_token
            if not (access_token := self.access_token):
                return response

            new_request = response.request.copy()
            new_request.headers["Authorization"] = f"Bearer {access_token}"
            new_request._auth_retry = True
            new_response = response.connection.send(new_request, **kwargs)
            new_response.history.append(response)
            return new_response

        return response

    def _client_session(self) -> requests.Session:
        """Build a requests Session with auth and the token-refresh hook.

        :return: A requests.Session object configured for this client
        """
        session = requests.Session()
        session.auth = ClientAuth(self)
        session.hooks["response"].append(self._handle_token_refresh)
        return session

    def get(
        self, uri_frag: str, timeout: int = DEFAULT_TIMEOUT_SECONDS
    ) -> str:
        """Submit a GET request to the server.

        :param uri_frag: endpoint for the GET request
        :param timeout: seconds to wait for a response before timing out
        :return: String containing the response from the server.
        """
        uri = urllib.parse.urljoin(self.server, uri_frag)
        try:
            req = self._client_session().get(uri, timeout=timeout)
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

    def post(
        self, uri_frag: str, data: dict, timeout: int = DEFAULT_TIMEOUT_SECONDS
    ) -> str:
        """Submit a POST request to the server.

        :param uri_frag: endpoint for the POST request
        :param data: dictionary of data to send in the POST request
        :param timeout: seconds to wait for a response before timing out
        :return: String containing the response from the server.
        """
        uri = urllib.parse.urljoin(self.server, uri_frag)
        try:
            req = self._client_session().post(uri, json=data, timeout=timeout)
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

    def get_status(self, job_id: str) -> str | None:
        """Get the status of a test job.

        :param job_id: ID for the test job
        :return: String containing the job_state for the specified job_id
        """
        try:
            endpoint = f"/v1/result/{job_id}"
            data = json.loads(self.get(endpoint))
            state = data.get("job_state")
        except OSError:
            logger.error("Unable to get status for job %s", job_id)
            state = "unknown"
        return state

    def get_results(self, job_id: str) -> dict:
        """Get the results of a test job.

        :param job_id: ID for the test job
        :return: dict containing the results for the specified job_id
        """
        try:
            endpoint = f"/v1/result/{job_id}"
            data = json.loads(self.get(endpoint))
        except OSError:
            logger.error("Unable to get results for job %s", job_id)
            data = {}
        return data

    def submit_job(self, job_data: dict) -> str | None:
        """Submit a test job to the testflinger server.

        :param job_data: dict of data for the job to submit
        :return: ID for the test job
        """
        endpoint = "/v1/job"
        response = self.post(endpoint, job_data)
        return json.loads(response).get("job_id")

    def cancel_job(self, job_id: str) -> None:
        """Tell the server to cancel a specified job_id."""
        try:
            self.post(f"/v1/job/{job_id}/action", {"action": "cancel"})
        except requests.exceptions.HTTPError as exc:
            # Ignore it if the job is already cancelled or completed
            if exc.response.status_code != HTTPStatus.BAD_REQUEST:
                raise
        except OSError:
            logger.error("Unable to cancel job %s", job_id)
            raise
