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
from testflinger_cli.enums import ServerRoles
from testflinger_cli.errors import AuthorizationError

from .conftest import URL


@pytest.mark.parametrize("state", ["offline", "maintenance"])
def test_set_agent_status_online(auth_fixture, capsys, requests_mock, state):
    """Validate we are able to change agent mode to online."""
    auth_fixture(ServerRoles.ADMIN)
    fake_agent = "fake_agent"
    fake_return = {
        "name": "fake_agent",
        "queues": ["fake"],
        "mode": state,
    }
    fake_send_agent_data = [{"mode": "online"}]

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

    requests_mock.get(f"{URL}/v1/agents/data/{fake_agent}", json=fake_return)
    requests_mock.post(
        f"{URL}/v1/agents/data/{fake_agent}", json=fake_send_agent_data
    )
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.admin_cli.set_agent_status()
    std = capsys.readouterr()
    assert "Agent fake_agent status is now: online" in std.out


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
    requests_mock.get(f"{URL}/v1/agents/data/{fake_agent}", json=fake_return)
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
    requests_mock.get(f"{URL}/v1/agents/data/{fake_agent}", json=fake_return)
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


def test_set_maintenance_without_comments(auth_fixture, requests_mock):
    """Validate status can't change to maintenance without comments."""
    auth_fixture(ServerRoles.ADMIN)
    fake_agent = "fake_agent"
    fake_return = {
        "name": "fake_agent",
        "queues": ["fake"],
        "mode": "online",
        "state": "waiting",
    }
    requests_mock.get(f"{URL}/v1/agents/data/{fake_agent}", json=fake_return)
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

    tfcli = testflinger_cli.TestflingerCli()
    with pytest.raises(SystemExit) as excinfo:
        tfcli.admin_cli.set_agent_status()
    assert (
        "Comment is required when setting agent status to maintenance"
        in str(excinfo.value)
    )


def test_set_maintenance_with_comment(auth_fixture, capsys, requests_mock):
    """Validate maintenance state can be set when comment is provided."""
    auth_fixture(ServerRoles.ADMIN)
    fake_agent = "fake_agent"
    fake_return = {
        "name": "fake_agent",
        "queues": ["fake"],
        "state": "waiting",
    }
    fake_send_agent_data = [
        {"mode": "maintenance", "comment": "Replacing hardware component"}
    ]
    requests_mock.get(f"{URL}/v1/agents/data/{fake_agent}", json=fake_return)
    requests_mock.post(
        f"{URL}/v1/agents/data/{fake_agent}", json=fake_send_agent_data
    )
    sys.argv = [
        "",
        "admin",
        "set",
        "agent-status",
        "--status",
        "maintenance",
        "--agents",
        fake_agent,
        "--comment",
        "Replacing hardware component",
    ]

    tfcli = testflinger_cli.TestflingerCli()
    tfcli.admin_cli.set_agent_status()
    std = capsys.readouterr()
    assert "Agent fake_agent status is now: maintenance" in std.out


def test_set_maintenance_comment_is_raw_not_templated(
    auth_fixture, capsys, requests_mock
):
    """The comment sent to the server must be the raw user-provided reason.

    Previously the CLI formatted the comment with a template embedding the
    user and a 'Reason:' prefix.  That responsibility now belongs to the
    server (via state_changed_by metadata).  The CLI must send the raw comment
    unchanged so the server can store it as the plain reason field.
    """
    auth_fixture(ServerRoles.ADMIN)
    fake_agent = "fake_agent"
    fake_return = {
        "name": "fake_agent",
        "queues": ["fake"],
        "state": "waiting",
    }
    raw_comment = "Replacing hardware component"
    requests_mock.get(f"{URL}/v1/agents/data/{fake_agent}", json=fake_return)
    post_mock = requests_mock.post(
        f"{URL}/v1/agents/data/{fake_agent}", json={}
    )
    sys.argv = [
        "",
        "admin",
        "set",
        "agent-status",
        "--status",
        "maintenance",
        "--agents",
        fake_agent,
        "--comment",
        raw_comment,
    ]

    tfcli = testflinger_cli.TestflingerCli()
    tfcli.admin_cli.set_agent_status()

    posted_body = post_mock.last_request.json()
    assert posted_body.get("comment") == raw_comment, (
        "CLI should send the raw comment; "
        "server is responsible for adding metadata like 'Set by user'"
    )
    # Ensure the old template strings are NOT present
    assert "Set to maintenance by" not in posted_body.get("comment", "")
    assert "Reason:" not in posted_body.get("comment", "")


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
    requests_mock.get(f"{URL}/v1/agents/data/{fake_agent}", json=fake_return)
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
    """Validate we receive a deferred message if agent under test phase."""
    auth_fixture(ServerRoles.ADMIN)
    fake_agent = "fake_agent"
    fake_return = {
        "name": fake_agent,
        "queues": ["fake"],
        "state": state,
    }
    requests_mock.get(f"{URL}/v1/agents/data/{fake_agent}", json=fake_return)
    sys.argv = [
        "",
        "admin",
        "set",
        "agent-status",
        "--status",
        "maintenance",
        "--agents",
        fake_agent,
        "--comment",
        "Scheduled lab maintenance",
    ]

    fake_send_agent_data = [{"mode": "maintenance", "comment": ""}]
    requests_mock.post(
        f"{URL}/v1/agents/data/{fake_agent}", json=fake_send_agent_data
    )
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.admin_cli.set_agent_status()
    std = capsys.readouterr()
    assert "Mode maintenance deferred until job completion" in std.out


def test_set_status_unknown_agent(auth_fixture, capsys, requests_mock):
    """Validate we skip non existing agents but modify the ones that exist."""
    auth_fixture(ServerRoles.ADMIN)
    fake_agents = ["fake_agent1", "fake_agent2"]
    fake_return = {
        "name": "fake_agent1",
        "queues": ["fake"],
        "mode": "online",
        "state": "waiting",
    }
    fake_send_agent_data = [{"mode": "online"}]

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

    requests_mock.get(f"{URL}/v1/agents/data/fake_agent1", json=fake_return)
    requests_mock.get(
        f"{URL}/v1/agents/data/fake_agent2", status_code=HTTPStatus.NOT_FOUND
    )
    requests_mock.post(
        f"{URL}/v1/agents/data/fake_agent1", json=fake_send_agent_data
    )
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.admin_cli.set_agent_status()
    std = capsys.readouterr()
    assert "Agent fake_agent1 status is now: online" in std.out
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

    requests_mock.get(f"{URL}/v1/client-permissions", json=fake_return)
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
        f"{URL}/v1/client-permissions/{fake_client_id}",
        status_code=HTTPStatus.NOT_FOUND,
    )
    requests_mock.put(
        f"{URL}/v1/client-permissions/{fake_client_id}",
        status_code=HTTPStatus.OK,
        text=f"Created permissions for client '{fake_client_id}'",
    )
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.admin_cli.set_client_permissions()
    std = capsys.readouterr()
    assert f"Created permissions for client '{fake_client_id}'" in std.out


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
        f"{URL}/v1/client-permissions/{fake_client_id}",
        status_code=HTTPStatus.NOT_FOUND,
    )
    requests_mock.put(
        f"{URL}/v1/client-permissions/{fake_client_id}",
        status_code=HTTPStatus.OK,
        text=f"Created permissions for client '{fake_client_id}'",
    )
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.admin_cli.set_client_permissions()
    std = capsys.readouterr()
    assert f"Created permissions for client '{fake_client_id}'" in std.out


def test_edit_client_permissions(auth_fixture, capsys, requests_mock):
    """Validate editing existing client_permissions when json is provided."""
    auth_fixture(ServerRoles.ADMIN)
    fake_client_id = "clientA"

    # Update just the role
    sys.argv = [
        "",
        "admin",
        "set",
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
        f"{URL}/v1/client-permissions/{fake_client_id}",
        status_code=HTTPStatus.OK,
        json=existing_data,
    )
    # Mock the PUT request for editing
    put_mock = requests_mock.put(
        URL + f"/v1/client-permissions/{fake_client_id}",
        status_code=HTTPStatus.OK,
        text=f"Updated permissions for client '{fake_client_id}'",
    )
    testflinger_cli.TestflingerCli().run()
    std = capsys.readouterr()
    assert f"Updated permissions for client '{fake_client_id}'" in std.out
    # Verify all permissions remain the same except the role
    updated_data = put_mock.last_request.json()

    # Only role should be updated
    assert len(updated_data) == 1
    assert updated_data["role"] == ServerRoles.MANAGER


def test_failed_set_client_due_schema_validation(
    auth_fixture, requests_mock, caplog
):
    """Test set permissions for client_id fails due to schema validation."""
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
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.admin_cli.set_client_permissions()
    assert "Validation error - max_reservation_time:" in caplog.text


def test_client_id_missing_from_permissions(auth_fixture):
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
        "set",
        "client-permissions",
        "--json",
        json.dumps(fake_permissions),
    ]
    with pytest.raises(SystemExit) as exc:
        testflinger_cli.TestflingerCli().run()
    assert "Error: client_id cannot be empty" in str(exc.value)


def test_create_client_permissions_with_email_argument(
    auth_fixture, capsys, requests_mock
):
    """Validate that email is sent in the PUT request body."""
    auth_fixture(ServerRoles.ADMIN)
    fake_client_id = "test-client"

    sys.argv = [
        "",
        "admin",
        "set",
        "client-permissions",
        "--testflinger-client-id",
        fake_client_id,
        "--testflinger-client-secret",
        "client-secret",
        "--email",
        "owner@example.com",
    ]

    requests_mock.get(
        f"{URL}/v1/client-permissions/{fake_client_id}",
        status_code=HTTPStatus.NOT_FOUND,
    )
    put_mock = requests_mock.put(
        f"{URL}/v1/client-permissions/{fake_client_id}",
        status_code=HTTPStatus.OK,
        text=f"Created permissions for client '{fake_client_id}'",
    )
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.run()
    std = capsys.readouterr()
    assert f"Created permissions for client '{fake_client_id}'" in std.out
    assert put_mock.last_request.json()["email"] == "owner@example.com"
