# Copyright (C) 2026 Canonical
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

"""Tests for the OIDC authenticated endpoints."""

from http import HTTPStatus
from unittest.mock import MagicMock, patch

import pytest
import requests

from testflinger.oidc import helpers

FAKE_DEVICE_AUTH_URL = "http://fake-idp/device/code"


@pytest.fixture
def device_auth_metadata():
    """Fake OIDC metadata with a device authorization endpoint.

    Tests aiming to verify OIDC device flow need to use this fixture
    given iam_server fixture does not support the device flow.
    """
    return {"device_authorization_endpoint": FAKE_DEVICE_AUTH_URL}


@pytest.fixture
def device_auth_response():
    """Fake successful device authorization response."""
    response = MagicMock()
    response.status_code = HTTPStatus.OK
    response.json.return_value = {
        "device_code": "test-device-code",
        "user_code": "ABCD-1234",
        "verification_uri": "http://fake-idp/device",
        "expires_in": 300,
        "interval": 5,
    }
    return response


def test_oidc_client_current_app(oidc_app):
    """Test that oidc_client returns the OIDC client from the current app."""
    app, _ = oidc_app
    with app.app_context():
        client = helpers.oidc_client()
        assert client is not None
        assert client.client_id == app.config["OIDC_CLIENT_ID"]
        assert client.client_secret == app.config["OIDC_CLIENT_SECRET"]


def test_oidc_metadata_current_app(oidc_app):
    """Test that oidc_metadata returns the metadata from the OIDC provider."""
    app, _ = oidc_app
    with app.app_context():
        metadata = helpers.oidc_metadata()
        assert isinstance(metadata, dict)
        assert "issuer" in metadata
        # iam_server fixture configuration may have a trailing slash
        assert metadata["issuer"] == app.config["OIDC_PROVIDER_ISSUER"].rstrip(
            "/"
        )  # noqa: E501


@patch("testflinger.oidc.helpers.requests.post")
@patch.object(helpers, "oidc_metadata")
def test_oidc_device_authorization_request(
    mock_metadata,
    mock_post,
    oidc_app,
    device_auth_metadata,
    device_auth_response,
):
    """Test device flow request to OIDC provider using current app's client."""
    mock_metadata.return_value = device_auth_metadata
    mock_post.return_value = device_auth_response
    app, _ = oidc_app
    with app.app_context():
        device_auth_endpoint = helpers.oidc_metadata().get(
            "device_authorization_endpoint"
        )
        response = helpers.oidc_post_request(
            device_auth_endpoint,
            data={"scope": "openid profile email"},
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code == HTTPStatus.OK
        assert "device_code" in response.json()


@patch("testflinger.oidc.helpers.requests.post")
@patch.object(helpers, "oidc_metadata")
def test_oidc_device_authorization_request_public_client(
    mock_metadata,
    mock_post,
    oidc_app,
    device_auth_metadata,
    device_auth_response,
):
    """Test request contains client_id in request body for public clients."""
    mock_metadata.return_value = device_auth_metadata
    mock_post.return_value = device_auth_response
    app, _ = oidc_app
    with app.app_context():
        # Simulate public client by removing client_secret
        app.oauth.oidc.client_secret = None
        device_auth_endpoint = helpers.oidc_metadata().get(
            "device_authorization_endpoint"
        )
        response = helpers.oidc_post_request(
            device_auth_endpoint,
            data={"scope": "openid profile email"},
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code == HTTPStatus.OK
        assert "device_code" in response.json()
        # Verify client_id was sent in the request body (not as Basic auth)
        call_kwargs = mock_post.call_args
        assert call_kwargs.kwargs["auth"] is None
        assert "client_id" in call_kwargs.kwargs["data"]


@patch("testflinger.oidc.helpers.requests.get")
def test_oidc_userinfo_request(mock_get, oidc_app):
    """Test getting user info from OIDC provider using current app's client."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "sub": "1234",
        "email": "testflinger@example.com",
    }
    mock_get.return_value = mock_response
    app, _ = oidc_app
    with app.app_context():
        userinfo = helpers.oidc_userinfo("valid-access-token")
        assert isinstance(userinfo, dict)
        assert "sub" in userinfo
        assert "email" in userinfo


def test_auth_init_aborts_if_device_auth_endpoint_missing(oidc_app):
    """Test /auth-init aborts if OIDC provider does not support device flow."""
    app, _ = oidc_app
    with app.app_context():
        response = app.test_client().post("/oidc/auth-init")
        # Given the iam_server fixture does not support device flow,
        # the endpoint should abort with 500 and a relevant message
        assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
        assert (
            b"OIDC provider does not support device authorization"
            in response.data
        )


@patch("testflinger.oidc.helpers.requests.post")
@patch.object(helpers, "oidc_metadata")
def test_auth_init_aborts_if_oidc_connection_error(
    mock_metadata, mock_post, oidc_app, device_auth_metadata
):
    """Test /auth-init aborts if OIDC provider connection fails."""
    app, _ = oidc_app
    mock_metadata.return_value = device_auth_metadata
    mock_post.side_effect = requests.RequestException("Connection error")
    with app.app_context():
        response = app.test_client().post("/oidc/auth-init")
        assert response.status_code == HTTPStatus.BAD_GATEWAY
        assert b"Failed to communicate with OIDC provider" in response.data


@patch("testflinger.oidc.helpers.requests.post")
@patch.object(helpers, "oidc_metadata")
def test_auth_init_aborts_if_device_code_missing(
    mock_metadata,
    mock_post,
    oidc_app,
    device_auth_metadata,
    device_auth_response,
):
    """Test /auth-init aborts if OIDC provider response lacks device_code."""
    app, _ = oidc_app
    mock_metadata.return_value = device_auth_metadata
    # Simulate missing device_code in the response
    device_auth_response.json.return_value.pop("device_code")
    mock_post.return_value = device_auth_response
    with app.app_context():
        response = app.test_client().post("/oidc/auth-init")
        assert response.status_code == HTTPStatus.BAD_GATEWAY
        assert b"OIDC provider response missing device_code" in response.data


@patch("testflinger.oidc.helpers.requests.post")
@patch.object(helpers, "oidc_metadata")
def test_auth_init_successful_request(
    mock_metadata,
    mock_post,
    oidc_app,
    device_auth_metadata,
    device_auth_response,
):
    """Test /auth-init returns request_id and other parameters on success."""
    app, mongo = oidc_app
    mock_metadata.return_value = device_auth_metadata
    mock_post.return_value = device_auth_response
    with app.app_context():
        response = app.test_client().post("/oidc/auth-init")
        assert response.status_code == HTTPStatus.OK
        data = response.get_json()
        assert "user_code" in data
        assert "verification_uri" in data
        assert "expires_in" in data
        assert "interval" in data

        # Device code should NOT be returned in the response
        # Instead of device_code, a unique request_id is returned for polling
        assert "device_code" not in data
        assert "request_id" in data

        # Verify device_code was stored in the database linked to request_id
        db_entry = mongo.device_codes.find_one(
            {"request_id": data["request_id"]}
        )
        assert db_entry is not None
        assert db_entry["device_code"] == "test-device-code"
        assert "expires_at" in db_entry


def test_auth_poll_aborts_if_request_id_invalid(oidc_app):
    """Test /auth-poll aborts if request_id is invalid or expired."""
    app, _ = oidc_app
    with app.app_context():
        # Given no device code was stored for this request_id,
        # the endpoint should abort
        response = app.test_client().post("/oidc/auth-poll/invalid-id")
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert b"Invalid or expired request_id" in response.data


@patch.object(helpers, "oidc_metadata")
def test_auth_poll_aborts_if_token_endpoint_missing(mock_metadata, oidc_app):
    """Test /auth-poll aborts if OIDC metadata is missing token_endpoint."""
    app, mongo = oidc_app
    # Metadata with no token_endpoint
    mock_metadata.return_value = {}
    with app.app_context():
        # Pre-seed a device code so the request_id lookup succeeds
        mongo.device_codes.insert_one(
            {
                "request_id": "test-request-id",
                "device_code": "test-device-code",
            }
        )
        response = app.test_client().post("/oidc/auth-poll/test-request-id")
        assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
        assert (
            b"OIDC provider metadata missing token endpoint" in response.data
        )


@patch("testflinger.oidc.helpers.requests.post")
def test_auth_poll_aborts_if_oidc_connection_error(mock_post, oidc_app):
    """Test /auth-poll aborts if OIDC provider connection fails."""
    app, mongo = oidc_app
    mock_post.side_effect = requests.RequestException("Connection error")
    with app.app_context():
        # Pre-seed a device code so the request_id lookup succeeds
        mongo.device_codes.insert_one(
            {
                "request_id": "test-request-id",
                "device_code": "test-device-code",
            }
        )

        response = app.test_client().post("/oidc/auth-poll/test-request-id")
        assert response.status_code == HTTPStatus.BAD_GATEWAY
        assert b"Failed to communicate with OIDC provider" in response.data


@pytest.mark.parametrize(
    "error_code, expected_status, device_code_removed",
    [
        ("authorization_pending", HTTPStatus.BAD_REQUEST, False),
        ("slow_down", HTTPStatus.BAD_REQUEST, False),
        ("access_denied", HTTPStatus.BAD_REQUEST, True),
    ],
)
@patch("testflinger.oidc.helpers.requests.post")
def test_auth_poll_token_error_responses(
    mock_post,
    oidc_app,
    error_code,
    expected_status,
    device_code_removed,
):
    """Test /auth-poll returns correct response for each IDP token error."""
    app, mongo = oidc_app
    mock_token_response = MagicMock()
    mock_token_response.status_code = HTTPStatus.BAD_REQUEST
    mock_token_response.json.return_value = {"error": error_code}
    mock_post.return_value = mock_token_response
    with app.app_context():
        mongo.device_codes.insert_one(
            {
                "request_id": "test-request-id",
                "device_code": "test-device-code",
            }
        )
        response = app.test_client().post("/oidc/auth-poll/test-request-id")

        # Validate the response status and body from the /auth-poll endpoint
        assert response.status_code == expected_status
        assert response.get_json()["error"] == error_code

        # Only the "access_denied" error should remove the device code from db
        db_entry = mongo.device_codes.find_one(
            {"request_id": "test-request-id"}
        )
        if device_code_removed:
            assert db_entry is None
        else:
            assert db_entry is not None


@patch("testflinger.oidc.helpers.oidc_userinfo")
@patch("testflinger.oidc.helpers.requests.post")
def test_auth_poll_not_register_malformed_userinfo(
    mock_post, mock_userinfo, oidc_app
):
    """Test /auth-poll aborts if OIDC provider returns malformed userinfo."""
    app, mongo = oidc_app
    mock_token_response = MagicMock()
    mock_token_response.status_code = HTTPStatus.OK
    mock_token_response.json.return_value = {
        "access_token": "fake-access-token"
    }
    mock_post.return_value = mock_token_response
    # No email in userinfo to simulate malformed response
    mock_userinfo.return_value = {"sub": "1234"}
    with app.app_context():
        # Pre-seed a device code so the request_id lookup succeeds
        mongo.device_codes.insert_one(
            {
                "request_id": "test-request-id",
                "device_code": "test-device-code",
            }
        )
        response = app.test_client().post("/oidc/auth-poll/test-request-id")
        assert response.status_code == HTTPStatus.BAD_GATEWAY
        assert (
            b"OIDC provider did not return an email address" in response.data
        )


@patch("testflinger.oidc.helpers.oidc_userinfo")
@patch("testflinger.oidc.helpers.requests.post")
def test_auth_poll_successful_registration(
    mock_post, mock_userinfo, oidc_app, user
):
    """Test /auth-poll successfully registers a new user on successful auth."""
    app, mongo = oidc_app
    mock_token_response = MagicMock()
    mock_token_response.status_code = HTTPStatus.OK
    mock_token_response.json.return_value = {
        "access_token": "fake-access-token"
    }
    mock_post.return_value = mock_token_response
    mock_userinfo.return_value = {
        "sub": "test-sub-1234",
        "email": user.emails[0],
        "name": user.user_name,
    }
    with app.app_context():
        mongo.device_codes.insert_one(
            {
                "request_id": "test-request-id",
                "device_code": "test-device-code",
            }
        )
        response = app.test_client().post("/oidc/auth-poll/test-request-id")
        assert response.status_code == HTTPStatus.OK
        data = response.get_json()

        # Verify Testflinger tokens are returned (not the OIDC tokens)
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "Bearer"  # noqa: S105
        assert "expires_in" in data

        # Device code must be removed after successful authentication
        assert (
            mongo.device_codes.find_one({"request_id": "test-request-id"})
            is None
        )

        # User must be registered in client_permissions
        # email is used as the client_id for OIDC users
        client_entry = mongo.client_permissions.find_one(
            {"client_id": user.emails[0]}
        )
        assert client_entry is not None
        assert client_entry["sub"] == "test-sub-1234"
