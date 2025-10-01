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

import json
import sys
from http import HTTPStatus

import pytest

import testflinger_cli
from testflinger_cli.consts import ServerRoles
from testflinger_cli.errors import AuthorizationError

from .test_cli import URL


@pytest.mark.parametrize("state", ["offline", "maintenance"])
def test_set_agent_status_online(auth_fixture, capsys, requests_mock, state):
    """Validate we are able to change agent status to online."""
    auth_fixture(ServerRoles.ADMIN)
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
def test_set_incorrect_agent_status(
    auth_fixture, capsys, requests_mock, state
):
    """Validate we can't modify status to online if at any testing stage."""
    auth_fixture(ServerRoles.ADMIN)
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

    tfcli = testflinger_cli.TestflingerCli()
    tfcli.admin_cli.set_agent_status()
    std = capsys.readouterr()
    assert f"Could not modify {fake_agent} in its current state" in std.out


def test_set_offline_without_comments(auth_fixture, requests_mock):
    """Validate status can't change to offline without comments."""
    auth_fixture(ServerRoles.ADMIN)
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

    tfcli = testflinger_cli.TestflingerCli()
    with pytest.raises(SystemExit) as excinfo:
        tfcli.admin_cli.set_agent_status()
    assert "Comment is required when setting agent status to offline" in str(
        excinfo.value
    )


@pytest.mark.parametrize("role", ["user", "contributor"])
def test_set_agent_status_with_unprivileged_user(
    auth_fixture, requests_mock, role
):
    """Validate status can't change if user doesn't have the right role."""
    auth_fixture(role)

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

    tfcli = testflinger_cli.TestflingerCli()
    with pytest.raises(AuthorizationError) as excinfo:
        tfcli.admin_cli.set_agent_status()
    assert "Authorization Error: Command requires role" in str(excinfo.value)


@pytest.mark.parametrize(
    "state", ["setup", "provision", "test", "allocate", "reserve"]
)
def test_deferred_offline_message(auth_fixture, capsys, requests_mock, state):
    """Validate we receive a deffered message if agent under test phase."""
    auth_fixture(ServerRoles.ADMIN)
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

    fake_send_agent_data = [{"state": "maintenance", "comment": ""}]
    requests_mock.post(
        URL + "/v1/agents/data/" + fake_agent, json=fake_send_agent_data
    )
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.admin_cli.set_agent_status()
    std = capsys.readouterr()
    assert "Status maintenance deferred until job completion" in std.out


def test_set_status_unknown_agent(auth_fixture, capsys, requests_mock):
    """Validate we skip non existing agents but modify the ones that exist."""
    auth_fixture(ServerRoles.ADMIN)
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


def test_get_all_client_permissions(auth_fixture, capsys, requests_mock):
    """Validate we get all client permissions if no client_id was specified."""
    auth_fixture(ServerRoles.ADMIN)
    fake_clients = {
        "clientA": ServerRoles.MANAGER,
        "clientB": ServerRoles.CONTRIBUTOR,
    }

    fake_return = [
        {
            "client_id": client_id,
            "max_priority": {"q1": 10},
            "allowed_queues": [],
            "max_reservation_time": {},
            "role": role,
        }
        for client_id, role in fake_clients.items()
    ]

    sys.argv = [
        "",
        "admin",
        "get",
        "client-permissions",
    ]

    requests_mock.get(URL + "/v1/client-permissions", json=fake_return)
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.admin_cli.get_client_permissions()
    std = capsys.readouterr()

    # Assert there are two clients and result matches
    json_return = json.loads(std.out)
    assert len(json_return) == 2
    assert json_return == fake_return


def test_get_single_client_permissions(auth_fixture, capsys, requests_mock):
    """Validate we get a one client permission when client_id is specified."""
    auth_fixture(ServerRoles.ADMIN)
    fake_client_id = "clientA"
    fake_return = {
        "client_id": fake_client_id,
        "max_priority": {"q1": 10},
        "allowed_queues": [],
        "max_reservation_time": {},
        "role": ServerRoles.MANAGER,
    }

    sys.argv = [
        "",
        "admin",
        "get",
        "client-permissions",
        "--testflinger-client-id",
        fake_client_id,
    ]

    requests_mock.get(
        URL + f"/v1/client-permissions/{fake_client_id}", json=fake_return
    )
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.admin_cli.get_client_permissions()
    std = capsys.readouterr()

    # Assert we get single client data
    json_return = json.loads(std.out)
    assert json_return == fake_return


@pytest.mark.parametrize(
    "role",
    [
        ServerRoles.USER,
        ServerRoles.CONTRIBUTOR,
        ServerRoles.MANAGER,
        ServerRoles.ADMIN,
    ],
)
def test_delete_client_permissions(auth_fixture, capsys, requests_mock, role):
    """Validate deleting client permissions only works for admin role."""
    auth_fixture(role)
    fake_client_id = "clientA"

    sys.argv = [
        "",
        "admin",
        "delete",
        "client-permissions",
        "--testflinger-client-id",
        fake_client_id,
    ]

    requests_mock.get(
        URL + f"/v1/client-permissions/{fake_client_id}",
        status_code=HTTPStatus.OK,
    )
    requests_mock.delete(
        URL + f"/v1/client-permissions/{fake_client_id}",
        status_code=HTTPStatus.OK,
    )
    tfcli = testflinger_cli.TestflingerCli()

    # Only admin should succeed
    if role != "admin":
        with pytest.raises(AuthorizationError) as excinfo:
            tfcli.admin_cli.delete_client_permissions()
        assert "Authorization Error: Command requires role" in str(
            excinfo.value
        )
    else:
        tfcli.admin_cli.delete_client_permissions()
        std = capsys.readouterr()
        assert f"Succesfully deleted {fake_client_id} from database" in std.out


def test_create_client_permissions_json(auth_fixture, capsys, requests_mock):
    """Validate creation of client_permissions when json is provided."""
    auth_fixture(ServerRoles.ADMIN)
    fake_client_id = "clientA"
    fake_permissions = {
        "client_id": fake_client_id,
        "max_priority": {"q1": 10},
        "max_reservation_time": {},
        "role": ServerRoles.CONTRIBUTOR,
    }

    sys.argv = [
        "",
        "admin",
        "set",
        "client-permissions",
        "--json",
        json.dumps(fake_permissions),
    ]

    # We need to mock that the client does not exists first
    requests_mock.get(
        URL + f"/v1/client-permissions/{fake_client_id}",
        status_code=HTTPStatus.NOT_FOUND,
    )
    requests_mock.post(
        URL + "/v1/client-permissions",
        status_code=HTTPStatus.OK,
    )
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.admin_cli.set_client_permissions()
    std = capsys.readouterr()
    assert f"Creating new client '{fake_client_id}'..." in std.out
    assert f"Client '{fake_client_id}' created successfully" in std.out


def test_create_client_permissions_arguments(
    auth_fixture, capsys, requests_mock
):
    """Validate creation of client_permissions using command line arguments."""
    auth_fixture(ServerRoles.ADMIN)
    fake_client_id = "clientA"

    sys.argv = [
        "",
        "admin",
        "set",
        "client-permissions",
        "--testflinger-client-id",
        fake_client_id,
        "--testflinger-client-secret",
        "client-secret",
        "--max-priority",
        '{"q1": 10}',
        "--max-reservation",
        '{"q1": 3600}',
        "--role",
        ServerRoles.CONTRIBUTOR,
    ]

    # We need to mock that the client does not exists first
    requests_mock.get(
        URL + f"/v1/client-permissions/{fake_client_id}",
        status_code=HTTPStatus.NOT_FOUND,
    )
    requests_mock.post(
        URL + "/v1/client-permissions",
        status_code=HTTPStatus.OK,
    )
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.admin_cli.set_client_permissions()
    std = capsys.readouterr()
    assert f"Creating new client '{fake_client_id}'..." in std.out
    assert f"Client '{fake_client_id}' created successfully" in std.out


def test_edit_client_permissions(auth_fixture, capsys, requests_mock):
    """Validate editing existing client_permissions when json is provided."""
    auth_fixture(ServerRoles.ADMIN)
    fake_client_id = "clientA"

    # Update just the role
    sys.argv = [
        "",
        "admin",
        "update",
        "client-permissions",
        "--testflinger-client-id",
        fake_client_id,
        "--role",
        ServerRoles.MANAGER,
    ]

    # Mock that the client exists with all permissions
    existing_data = {
        "client_id": fake_client_id,
        "max_priority": {"q1": 10},
        "allowed_queues": [],
        "max_reservation_time": {"q1": 3600},
        "role": ServerRoles.CONTRIBUTOR,
    }
    requests_mock.get(
        URL + f"/v1/client-permissions/{fake_client_id}",
        status_code=HTTPStatus.OK,
        json=existing_data,
    )
    # Mock the PUT request for editing
    put_mock = requests_mock.put(
        URL + f"/v1/client-permissions/{fake_client_id}",
        status_code=HTTPStatus.OK,
    )
    tfcli = testflinger_cli.TestflingerCli().run()
    std = capsys.readouterr()
    assert (
        f"Client '{fake_client_id}' permissions updated successfully"
        in std.out
    )
    # Verify all permissions remain the same except the role
    updated_data = put_mock.last_request.json()

    # Verify existing fields are preserved and only role is updated
    for permission in [
        "max_priority",
        "allowed_queues",
        "max_reservation_time",
    ]:
        assert updated_data[permission] == existing_data[permission]

    # Only role should be updated
    assert updated_data["role"] == ServerRoles.MANAGER


def test_failed_client_creation_schema_validation(
    auth_fixture, capsys, requests_mock, caplog
):
    """Validate creation of client_id fails due to schema validation."""
    auth_fixture(ServerRoles.ADMIN)
    fake_client_id = "clientA"
    # missing max_reservation_time for creation
    fake_permissions = {
        "client_id": fake_client_id,
        "max_priority": {"q1": 10},
        "role": ServerRoles.CONTRIBUTOR,
    }

    # Using JSON for creation for simplicity
    sys.argv = [
        "",
        "admin",
        "set",
        "client-permissions",
        "--json",
        json.dumps(fake_permissions),
    ]

    # We need to mock that the client does not exists first
    requests_mock.get(
        f"{URL}/v1/client-permissions/{fake_client_id}",
        status_code=HTTPStatus.NOT_FOUND,
    )
    requests_mock.post(
        f"{URL}/v1/client-permissions",
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        json={
            "message": (
                "Validation error - max_reservation_time: "
                "['Missing data for required field.']"
            )
        },
    )
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.admin_cli.set_client_permissions()
    std = capsys.readouterr()
    assert f"Creating new client '{fake_client_id}'..." in std.out
    assert "Validation error - max_reservation_time:" in caplog.text


@pytest.mark.parametrize("command", ["set", "update"])
def test_client_id_missing_from_permissions(auth_fixture, command):
    """Validate creation and update of client_id fails due to missing id."""
    auth_fixture(ServerRoles.ADMIN)
    # missing client_id from permission JSON
    fake_permissions = {
        "max_reservation_time": {},
        "max_priority": {"q1": 10},
        "role": ServerRoles.CONTRIBUTOR,
    }

    # Using JSON for creation/update
    sys.argv = [
        "",
        "admin",
        command,
        "client-permissions",
        "--json",
        json.dumps(fake_permissions),
    ]
    with pytest.raises(SystemExit) as exc:
        testflinger_cli.TestflingerCli().run()
    assert "Error: client_id cannot be empty" in str(exc.value)


def test_update_fail_during_schema_validation(
    auth_fixture, requests_mock, caplog
):
    """Validate update of client_id fails due to schema validation."""
    auth_fixture(ServerRoles.ADMIN)
    fake_client_id = "clientA"
    # missing max_reservation_time for update in JSON data
    fake_permissions = {
        "client_id": fake_client_id,
        "max_priority": {"q1": 10},
        "role": ServerRoles.CONTRIBUTOR,
    }

    # Using JSON for creation for simplicity
    sys.argv = [
        "",
        "admin",
        "update",
        "client-permissions",
        "--json",
        json.dumps(fake_permissions),
    ]

    # We need to mock that the client exists
    existing_permissions = {
        "client_id": fake_client_id,
        "max_priority": {},
        "max_reservation_time": {},
        "role": ServerRoles.CONTRIBUTOR,
    }
    requests_mock.get(
        f"{URL}/v1/client-permissions/{fake_client_id}",
        status_code=HTTPStatus.OK,
        json=existing_permissions,
    )
    requests_mock.put(
        f"{URL}/v1/client-permissions/{fake_client_id}",
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        json={
            "message": (
                "Validation error - max_reservation_time: "
                "['Missing data for required field.']"
            )
        },
    )
    testflinger_cli.TestflingerCli().run()
    assert "Validation error - max_reservation_time:" in caplog.text


def test_create_fail_if_client_exists(auth_fixture, requests_mock, caplog):
    """Validate client creation fails if already exists."""
    auth_fixture(ServerRoles.ADMIN)
    fake_client_id = "clientA"
    # Mock permissions to send to server
    fake_permissions = {
        "client_id": fake_client_id,
        "max_priority": {},
        "max_reservation_time": {},
        "role": ServerRoles.CONTRIBUTOR,
    }

    # Using JSON for attempting to create
    sys.argv = [
        "",
        "admin",
        "set",
        "client-permissions",
        "--json",
        json.dumps(fake_permissions),
    ]

    # We need to mock that the client exists
    requests_mock.get(
        f"{URL}/v1/client-permissions/{fake_client_id}",
        status_code=HTTPStatus.OK,
        json=fake_permissions,
    )
    testflinger_cli.TestflingerCli().run()
    assert "Client id clientA already exists" in caplog.text
    assert (
        "For updating client permissions, please use the update command."
        in caplog.text
    )
