# Copyright (C) 2026 Canonical
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

"""Unit tests for TFClient authentication."""

from http import HTTPStatus
from unittest.mock import patch

import pytest
import requests

from testflinger_device_connectors.devices.multi.tfclient import TFClient

SERVER_URL = "http://testflinger.local"
CLIENT_ID = "multi-device-connector"
SECRET_KEY = "supersecret"  # noqa: S105
ACCESS_TOKEN = "access-token-abc123"  # noqa: S105


@pytest.fixture
def client():
    """TFClient instance with credentials configured."""
    return TFClient(url=SERVER_URL, client_id=CLIENT_ID, secret_key=SECRET_KEY)


@pytest.fixture
def unauthenticated_client():
    """TFClient instance with no credentials configured."""
    return TFClient(url=SERVER_URL)


def test_access_token_no_credentials_returns_none(unauthenticated_client):
    """access_token returns None when no credentials are configured."""
    assert unauthenticated_client.access_token is None


def test_access_token_returns_none_on_missing_arg():
    """access_token returns None when any credential argument is absent."""
    client = TFClient(url=SERVER_URL, client_id=CLIENT_ID)
    assert client.access_token is None

    client = TFClient(url=SERVER_URL, secret_key=SECRET_KEY)
    assert client.access_token is None


@patch("testflinger_device_connectors.devices.multi.tfclient.requests.post")
def test_access_token_successful_exchange(mock_post, client):
    """access_token exchanges credentials and returns the access token."""
    mock_post.return_value.raise_for_status.return_value = None
    mock_post.return_value.json.return_value = {"access_token": ACCESS_TOKEN}

    assert client.access_token == ACCESS_TOKEN

    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert "/v1/oauth2/token" in call_kwargs.args[0]
    assert "Basic" in call_kwargs.kwargs["headers"]["Authorization"]


@patch(
    "testflinger_device_connectors.devices.multi.tfclient.requests.post",
    side_effect=requests.exceptions.RequestException("connection error"),
)
def test_access_token_server_error_returns_none(mock_post, client):
    """access_token returns None when the server returns an error."""
    assert client.access_token is None


@patch(
    "testflinger_device_connectors.devices.multi.tfclient.requests.post",
)
def test_access_token_is_cached(mock_post, client):
    """access_token calls the server only once across multiple accesses."""
    mock_post.return_value.raise_for_status.return_value = None
    mock_post.return_value.json.return_value = {"access_token": ACCESS_TOKEN}

    first = client.access_token
    second = client.access_token

    assert first == second == ACCESS_TOKEN
    assert mock_post.call_count == 1


@patch("testflinger_device_connectors.devices.multi.tfclient.requests.post")
def test_handle_token_refresh_replays_request_on_401(
    mock_post, mocker, client
):
    """Test the request is replayed with a refreshed token on 401."""
    mock_post.return_value.raise_for_status.return_value = None
    mock_post.return_value.json.return_value = {"access_token": ACCESS_TOKEN}

    # Pre-seed the cache with a stale token to simulate expiry
    old_token = "old-token-stale"
    client.__dict__["access_token"] = old_token

    original_request = mocker.MagicMock()
    original_request._auth_retry = False
    original_request.headers = {}
    copied_request = mocker.MagicMock()
    copied_request.headers = {}
    original_request.copy.return_value = copied_request
    original_response = mocker.MagicMock()
    original_response.status_code = HTTPStatus.UNAUTHORIZED
    original_response.request = original_request
    original_response.content = b""

    retry_response = mocker.MagicMock()
    retry_response.status_code = HTTPStatus.OK
    retry_response.history = []
    original_response.connection.send.return_value = retry_response

    result = client._handle_token_refresh(original_response)

    assert result is retry_response
    # Verify the replayed request carries the new token, not the stale one
    assert copied_request.headers["Authorization"] == (
        f"Bearer {ACCESS_TOKEN}"
    )
    assert copied_request.headers["Authorization"] != f"Bearer {old_token}"
    assert copied_request._auth_retry is True


def test_handle_token_refresh_no_retry_loop(mocker, client):
    """Hook returns the original response if _auth_retry is already set."""
    request = mocker.MagicMock()
    request._auth_retry = True
    response = mocker.MagicMock()
    response.status_code = HTTPStatus.UNAUTHORIZED
    response.request = request

    result = client._handle_token_refresh(response)

    assert result is response
    response.connection.send.assert_not_called()


def test_get_attaches_bearer_header(mocker, client):
    """GET requests include Authorization: Bearer when credentials set."""
    mocker.patch(
        "testflinger_device_connectors.devices.multi.tfclient.requests.post",
        return_value=mocker.MagicMock(
            raise_for_status=mocker.MagicMock(return_value=None),
            json=mocker.MagicMock(return_value={"access_token": ACCESS_TOKEN}),
        ),
    )
    mock_session = mocker.patch(
        "testflinger_device_connectors.devices.multi.tfclient.requests.Session"
    )
    mock_session.return_value.get.return_value = mocker.MagicMock(
        status_code=HTTPStatus.OK,
        text="ok",
        raise_for_status=mocker.MagicMock(),
    )

    client.get("/v1/result/some-job-id")

    session_instance = mock_session.return_value
    assert session_instance.auth is not None
    prepared = mocker.MagicMock()
    prepared.headers = {}
    session_instance.auth(prepared)
    assert prepared.headers.get("Authorization") == f"Bearer {ACCESS_TOKEN}"


def test_unauthenticated_client_sends_no_header(
    mocker, unauthenticated_client
):
    """Requests have no Authorization header when no credentials configured."""
    prepared = mocker.MagicMock()
    prepared.headers = {}

    session = unauthenticated_client._client_session()
    session.auth(prepared)

    assert "Authorization" not in prepared.headers
