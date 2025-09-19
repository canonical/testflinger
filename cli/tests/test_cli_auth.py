# Copyright (C) 2024 Canonical
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
"""Unit Test for all cli commands that require authentication."""

import json
import sys
import uuid
from http import HTTPStatus

import pytest

import testflinger_cli
from testflinger_cli.consts import ServerRoles
from testflinger_cli.errors import InvalidTokenError
from .test_cli import URL


def test_submit_with_priority(tmp_path, requests_mock, monkeypatch):
    """Tests authorization of jobs submitted with priority."""
    job_id = str(uuid.uuid1())
    job_data = {
        "job_queue": "fake",
        "job_priority": 100,
    }
    job_file = tmp_path / "test.json"
    job_file.write_text(json.dumps(job_data))

    # Define variables for authentication
    monkeypatch.setenv("TESTFLINGER_CLIENT_ID", "my_client_id")
    monkeypatch.setenv("TESTFLINGER_SECRET_KEY", "my_secret_key")
    fake_return = {
        "access_token": "fake_jwt_token",
        "token_type": "Bearer",
        "expires_in": 30,
        "refresh_token": "fake_refresh_token",
    }
    requests_mock.post(f"{URL}/v1/oauth2/token", json=fake_return)

    sys.argv = ["", "submit", str(job_file)]
    tfcli = testflinger_cli.TestflingerCli()
    mock_response = {"job_id": job_id}
    requests_mock.post(f"{URL}/v1/job", json=mock_response)
    requests_mock.get(
        URL + "/v1/queues/fake/agents",
        json=[{"name": "fake_agent", "state": "waiting"}],
    )
    tfcli.submit()
    history = requests_mock.request_history
    assert len(history) == 3
    assert history[0].path == "/v1/oauth2/token"
    assert history[2].path == "/v1/job"
    assert history[2].headers.get("Authorization") == "Bearer fake_jwt_token"


def test_submit_token_timeout_retry(tmp_path, requests_mock, monkeypatch):
    """Tests job submission retries 3 times when token has expired."""
    job_data = {
        "job_queue": "fake",
        "job_priority": 100,
    }
    job_file = tmp_path / "test.json"
    job_file.write_text(json.dumps(job_data))

    # Define variables for authentication
    monkeypatch.setenv("TESTFLINGER_CLIENT_ID", "my_client_id")
    monkeypatch.setenv("TESTFLINGER_SECRET_KEY", "my_secret_key")
    fake_return = {
        "access_token": "fake_jwt_token",
        "token_type": "Bearer",
        "expires_in": 30,
        "refresh_token": "fake_refresh_token",
    }
    requests_mock.post(f"{URL}/v1/oauth2/token", json=fake_return)
    requests_mock.post(f"{URL}/v1/oauth2/refresh", json=fake_return)

    sys.argv = ["", "submit", str(job_file)]
    tfcli = testflinger_cli.TestflingerCli()
    requests_mock.post(
        f"{URL}/v1/job", text="Token has expired", status_code=401
    )
    requests_mock.get(
        URL + "/v1/queues/fake/agents",
        json=[{"name": "fake_agent", "state": "waiting"}],
    )
    with pytest.raises(SystemExit) as exc_info:
        tfcli.submit()
        assert "Token has expired" in exc_info.value

    history = requests_mock.request_history
    assert len(history) == 7
    assert history[0].path == "/v1/oauth2/token"
    assert history[2].path == "/v1/job"
    assert history[3].path == "/v1/oauth2/refresh"
    assert history[4].path == "/v1/job"
    assert history[5].path == "/v1/oauth2/refresh"
    assert history[6].path == "/v1/job"


def test_retrieve_regular_user_role(tmp_path, requests_mock):
    """Test that we get a regular user if no auth is made."""
    job_data = {
        "job_queue": "fake",
        "job_priority": 100,
    }
    job_file = tmp_path / "test.json"
    job_file.write_text(json.dumps(job_data))

    requests_mock.post(f"{URL}/v1/oauth2/token")
    sys.argv = ["", "submit", str(job_file)]
    tfcli = testflinger_cli.TestflingerCli()
    role = tfcli.auth.get_user_role()

    assert tfcli.auth.is_authenticated() is False
    assert role == "user"


def test_user_authenticated_with_role(auth_fixture, tmp_path, requests_mock):
    """Test user is able to authenticate and there is role defined."""
    auth_fixture(ServerRoles.ADMIN)
    job_data = {
        "job_queue": "fake",
        "job_priority": 100,
    }
    job_file = tmp_path / "test.json"
    job_file.write_text(json.dumps(job_data))

    expected_role = ServerRoles.ADMIN

    sys.argv = ["", "submit", str(job_file)]
    tfcli = testflinger_cli.TestflingerCli()
    role = tfcli.auth.get_user_role()

    assert tfcli.auth.is_authenticated() is True
    assert role == expected_role


def test_default_auth_user_role(auth_fixture, tmp_path, requests_mock):
    """Test we are able to get default user for legacy users."""
    auth_fixture(ServerRoles.CONTRIBUTOR)
    job_data = {
        "job_queue": "fake",
        "job_priority": 100,
    }
    job_file = tmp_path / "test.json"
    job_file.write_text(json.dumps(job_data))

    expected_role = ServerRoles.CONTRIBUTOR

    sys.argv = ["", "submit", str(job_file)]
    tfcli = testflinger_cli.TestflingerCli()
    role = tfcli.auth.get_user_role()

    assert tfcli.auth.is_authenticated() is True
    assert role == expected_role


def test_authorization_error(tmp_path, requests_mock, monkeypatch):
    """Test authorization error raises if received 403 from server."""
    job_data = {
        "job_queue": "fake",
        "job_priority": 100,
    }
    job_file = tmp_path / "test.json"
    job_file.write_text(json.dumps(job_data))

    # Define variables for authentication
    monkeypatch.setenv("TESTFLINGER_CLIENT_ID", "my_client_id")
    monkeypatch.setenv("TESTFLINGER_SECRET_KEY", "my_secret_key")

    requests_mock.post(
        f"{URL}/v1/oauth2/token", status_code=HTTPStatus.FORBIDDEN
    )

    sys.argv = ["", "submit", str(job_file)]
    with pytest.raises(SystemExit) as err:
        testflinger_cli.TestflingerCli()
    assert "Authorization error received from server" in str(err.value)


def test_authentication_error(tmp_path, requests_mock, monkeypatch):
    """Test authentication error raises if received 401 from server."""
    job_data = {
        "job_queue": "fake",
        "job_priority": 100,
    }
    job_file = tmp_path / "test.json"
    job_file.write_text(json.dumps(job_data))

    # Define variables for authentication
    monkeypatch.setenv("TESTFLINGER_CLIENT_ID", "my_client_id")
    monkeypatch.setenv("TESTFLINGER_SECRET_KEY", "my_secret_key")

    requests_mock.post(
        f"{URL}/v1/oauth2/token", status_code=HTTPStatus.UNAUTHORIZED
    )

    sys.argv = ["", "submit", str(job_file)]
    with pytest.raises(SystemExit) as err:
        testflinger_cli.TestflingerCli()
    assert "Authentication with Testflinger server failed" in str(err.value)


def test_cli_login(auth_fixture, capsys):
    """Test authentication succeeds when running login command."""
    auth_fixture(ServerRoles.CONTRIBUTOR)

    sys.argv = ["", "login"]
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.login()
    std = capsys.readouterr()
    # Make sure login also stores refresh token
    refresh_token = tfcli.auth.get_stored_refresh_token()

    assert refresh_token is not None
    assert "Successfully authenticated as user" in std.out


def test_multiple_login_clear_refresh_token(auth_fixture):
    """Test multiple user login clears refresh_token and issue new one."""
    auth_fixture(ServerRoles.CONTRIBUTOR)

    sys.argv = ["", "login"]
    tfcli = testflinger_cli.TestflingerCli()

    # Initial login
    tfcli.login()
    initial_token = tfcli.auth.get_stored_refresh_token()

    # Reattempt login with different role to simulate different logins
    auth_fixture(ServerRoles.MANAGER)
    tfcli.login()
    reauthenticated_token = tfcli.auth.get_stored_refresh_token()

    assert initial_token != reauthenticated_token


def test_refresh_token_expired(tmp_path, requests_mock, monkeypatch):
    """Test scenario where refresh_token is no longer valid."""
    job_data = {
        "job_queue": "fake",
        "job_priority": 100,
    }
    job_file = tmp_path / "test.json"
    job_file.write_text(json.dumps(job_data))

    # Define variables for authentication, not using fixture to mock fail auth
    monkeypatch.setenv("TESTFLINGER_CLIENT_ID", "my_client_id")
    monkeypatch.setenv("TESTFLINGER_SECRET_KEY", "my_secret_key")
    fake_return = {
        "access_token": "fake_jwt_token",
        "token_type": "Bearer",
        "expires_in": 30,
        "refresh_token": "fake_refresh_token",
    }
    requests_mock.post(f"{URL}/v1/oauth2/token", json=fake_return)

    sys.argv = ["", "submit", str(job_file)]
    tfcli = testflinger_cli.TestflingerCli()

    # Mock job submission to fail due to expired access_token
    requests_mock.post(
        f"{URL}/v1/job",
        text="Token has expired",
        status_code=HTTPStatus.UNAUTHORIZED,
    )
    # Mock refresh endpoint attempts to get new access_token fails
    requests_mock.post(
        f"{URL}/v1/oauth2/refresh",
        text="Refresh token expired",
        status_code=HTTPStatus.BAD_REQUEST,
    )
    # Mock agents endpoint for available agents
    requests_mock.get(
        URL + "/v1/queues/fake/agents",
        json=[{"name": "fake_agent", "state": "waiting"}],
    )

    with pytest.raises(InvalidTokenError) as exc:
        tfcli.submit()

    assert "Please reauthenticate with server" in str(exc.value)

    history = requests_mock.request_history
    assert len(history) >= 3
    assert history[0].path == "/v1/oauth2/token"
    assert history[2].path == "/v1/job"
    assert any(req.path == "/v1/oauth2/refresh" for req in history)
