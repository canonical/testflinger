# Copyright (C) 2022 Canonical
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

"""Unit tests for admin commands from testflinger-cli ."""

import sys
from http import HTTPStatus

import jwt
import pytest

import testflinger_cli
from testflinger_cli.errors import AuthorizationError
from testflinger_cli.tests.test_cli import URL


@pytest.mark.parametrize("state", ["offline", "maintenance"])
def test_set_agent_status_online(capsys, requests_mock, state, monkeypatch):
    """Validate we are able to change agent status to online."""
    fake_agent = "fake_agent"
    fake_return = {
        "name": "fake_agent",
        "queues": ["fake"],
        "state": state,
    }
    fake_send_agent_data = [{"state": "waiting", "comment": ""}]

    sys.argv = [
        "",
        "admin",
        "set",
        "agent-status",
        "--status",
        "online",
        "--agents",
        fake_agent,
    ]

    # Define variables for authentication
    monkeypatch.setenv("TESTFLINGER_CLIENT_ID", "my_client_id")
    monkeypatch.setenv("TESTFLINGER_SECRET_KEY", "my_secret_key")

    expected_role = "admin"
    fake_payload = {
        "permissions": {"client_id": "my_client_id", "role": expected_role}
    }
    fake_jwt_signing_key = "my-secret"
    fake_jwt_token = jwt.encode(
        fake_payload, fake_jwt_signing_key, algorithm="HS256"
    )
    requests_mock.post(f"{URL}/v1/oauth2/token", text=fake_jwt_token)

    requests_mock.get(URL + "/v1/agents/data/" + fake_agent, json=fake_return)
    requests_mock.post(
        URL + "/v1/agents/data/" + fake_agent, json=fake_send_agent_data
    )
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.admin_cli.set_agent_status()
    std = capsys.readouterr()
    assert "Agent fake_agent status is now: waiting" in std.out


@pytest.mark.parametrize(
    "state", ["setup", "provision", "test", "allocate", "reserve"]
)
def test_set_incorrect_agent_status(capsys, requests_mock, state, monkeypatch):
    """Validate we can't modify status to online if at any testing stage."""
    fake_agent = "fake_agent"
    fake_return = {
        "name": fake_agent,
        "queues": ["fake"],
        "state": state,
    }
    requests_mock.get(URL + "/v1/agents/data/" + fake_agent, json=fake_return)
    sys.argv = [
        "",
        "admin",
        "set",
        "agent-status",
        "--status",
        "online",
        "--agents",
        fake_agent,
    ]

    # Define variables for authentication
    monkeypatch.setenv("TESTFLINGER_CLIENT_ID", "my_client_id")
    monkeypatch.setenv("TESTFLINGER_SECRET_KEY", "my_secret_key")

    expected_role = "admin"
    fake_payload = {
        "permissions": {"client_id": "my_client_id", "role": expected_role}
    }
    fake_jwt_signing_key = "my-secret"
    fake_jwt_token = jwt.encode(
        fake_payload, fake_jwt_signing_key, algorithm="HS256"
    )
    requests_mock.post(f"{URL}/v1/oauth2/token", text=fake_jwt_token)

    tfcli = testflinger_cli.TestflingerCli()
    tfcli.admin_cli.set_agent_status()
    std = capsys.readouterr()
    assert f"Could not modify {fake_agent} in its current state" in std.out


def test_set_offline_without_comments(requests_mock, monkeypatch):
    """Validate status can't change to offline without comments."""
    fake_agent = "fake_agent"
    fake_return = {
        "name": "fake_agent",
        "queues": ["fake"],
        "state": "waiting",
    }
    requests_mock.get(URL + "/v1/agents/data/" + fake_agent, json=fake_return)
    sys.argv = [
        "",
        "admin",
        "set",
        "agent-status",
        "--status",
        "offline",
        "--agents",
        fake_agent,
    ]

    # Define variables for authentication
    monkeypatch.setenv("TESTFLINGER_CLIENT_ID", "my_client_id")
    monkeypatch.setenv("TESTFLINGER_SECRET_KEY", "my_secret_key")

    expected_role = "admin"
    fake_payload = {
        "permissions": {"client_id": "my_client_id", "role": expected_role}
    }
    fake_jwt_signing_key = "my-secret"
    fake_jwt_token = jwt.encode(
        fake_payload, fake_jwt_signing_key, algorithm="HS256"
    )
    requests_mock.post(f"{URL}/v1/oauth2/token", text=fake_jwt_token)

    tfcli = testflinger_cli.TestflingerCli()
    with pytest.raises(SystemExit) as excinfo:
        tfcli.admin_cli.set_agent_status()
    assert "Comment is required when setting agent status to offline" in str(
        excinfo.value
    )


@pytest.mark.parametrize("role", ["user", "contributor"])
def test_set_agent_status_with_unprivileged_user(
    requests_mock, monkeypatch, role
):
    """Validate status can't change if user doesn't have the right role."""
    fake_agent = "fake_agent"
    fake_return = {
        "name": "fake_agent",
        "queues": ["fake"],
        "state": "waiting",
    }
    requests_mock.get(URL + "/v1/agents/data/" + fake_agent, json=fake_return)
    sys.argv = [
        "",
        "admin",
        "set",
        "agent-status",
        "--status",
        "offline",
        "--agents",
        fake_agent,
    ]

    # Define variables for authentication
    monkeypatch.setenv("TESTFLINGER_CLIENT_ID", "my_client_id")
    monkeypatch.setenv("TESTFLINGER_SECRET_KEY", "my_secret_key")

    fake_payload = {"permissions": {"client_id": "my_client_id", "role": role}}
    fake_jwt_signing_key = "my-secret"
    fake_jwt_token = jwt.encode(
        fake_payload, fake_jwt_signing_key, algorithm="HS256"
    )
    requests_mock.post(f"{URL}/v1/oauth2/token", text=fake_jwt_token)

    tfcli = testflinger_cli.TestflingerCli()
    with pytest.raises(AuthorizationError) as excinfo:
        tfcli.admin_cli.set_agent_status()
    assert "Authorization Error: Command requires role" in str(excinfo.value)


@pytest.mark.parametrize(
    "state", ["setup", "provision", "test", "allocate", "reserve"]
)
def test_deferred_offline_message(capsys, requests_mock, state, monkeypatch):
    """Validate we receive a deffered message if agent under test phase."""
    fake_agent = "fake_agent"
    fake_return = {
        "name": fake_agent,
        "queues": ["fake"],
        "state": state,
    }
    requests_mock.get(URL + "/v1/agents/data/" + fake_agent, json=fake_return)
    sys.argv = [
        "",
        "admin",
        "set",
        "agent-status",
        "--status",
        "maintenance",
        "--agents",
        fake_agent,
    ]

    # Define variables for authentication
    monkeypatch.setenv("TESTFLINGER_CLIENT_ID", "my_client_id")
    monkeypatch.setenv("TESTFLINGER_SECRET_KEY", "my_secret_key")

    expected_role = "admin"
    fake_payload = {
        "permissions": {"client_id": "my_client_id", "role": expected_role}
    }
    fake_jwt_signing_key = "my-secret"
    fake_jwt_token = jwt.encode(
        fake_payload, fake_jwt_signing_key, algorithm="HS256"
    )
    requests_mock.post(f"{URL}/v1/oauth2/token", text=fake_jwt_token)

    fake_send_agent_data = [{"state": "maintenance", "comment": ""}]
    requests_mock.post(
        URL + "/v1/agents/data/" + fake_agent, json=fake_send_agent_data
    )
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.admin_cli.set_agent_status()
    std = capsys.readouterr()
    assert "Status maintenance deferred until job completion" in std.out


def test_set_status_unknown_agent(capsys, requests_mock, monkeypatch):
    """Validate we skip non existing agents but modify the ones that exist."""
    fake_agents = ["fake_agent1", "fake_agent2"]
    fake_return = {
        "name": "fake_agent1",
        "queues": ["fake"],
        "state": "waiting",
    }
    fake_send_agent_data = [{"state": "offline", "comment": ""}]

    sys.argv = [
        "",
        "admin",
        "set",
        "agent-status",
        "--status",
        "online",
        "--agents",
        *fake_agents,
    ]

    # Define variables for authentication
    monkeypatch.setenv("TESTFLINGER_CLIENT_ID", "my_client_id")
    monkeypatch.setenv("TESTFLINGER_SECRET_KEY", "my_secret_key")

    expected_role = "admin"
    fake_payload = {
        "permissions": {"client_id": "my_client_id", "role": expected_role}
    }
    fake_jwt_signing_key = "my-secret"
    fake_jwt_token = jwt.encode(
        fake_payload, fake_jwt_signing_key, algorithm="HS256"
    )
    requests_mock.post(f"{URL}/v1/oauth2/token", text=fake_jwt_token)

    requests_mock.get(URL + "/v1/agents/data/fake_agent1", json=fake_return)
    requests_mock.get(
        URL + "/v1/agents/data/fake_agent2", status_code=HTTPStatus.NOT_FOUND
    )
    requests_mock.post(
        URL + "/v1/agents/data/fake_agent1", json=fake_send_agent_data
    )
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.admin_cli.set_agent_status()
    std = capsys.readouterr()
    assert "Agent fake_agent1 status is now: waiting" in std.out
    assert "Agent fake_agent2 does not exist." in std.out
