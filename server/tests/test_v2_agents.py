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
#
"""Unit tests for the agent endpoints of the Testflinger v2 API."""

import time
from http import HTTPStatus

from testflinger_common.enums import ServerRoles

from testflinger import database
from tests.utilities import get_access_token_header

# ---------------------------------------------------------------------------
# POST /v2/agents/{name}/data  — agent heartbeat
# ---------------------------------------------------------------------------


def test_agents_post_mode_change_is_timestamped(mongo_app, agent_auth_header):
    """Posting a mode change stamps mode.changed_at (no attribution for agent
    reports). Mode is stored as nested document: {value, changed_at,
    changed_by}.
    """
    app, mongo = mongo_app
    agent_name = "agent1"

    output = app.post(
        f"/v2/agents/{agent_name}/data",
        json={"mode": "offline"},
        headers=agent_auth_header,
    )

    assert HTTPStatus.OK == output.status_code
    record = mongo.agents.find_one({"name": agent_name})
    assert record["mode"]["value"] == "offline"
    assert record["mode"]["changed_at"] is not None
    # Agent reports do not set changed_by (only admin commands do)
    assert "changed_by" not in record["mode"]


def test_agents_post_uses_upsert_agent_document(
    mongo_app, agent_auth_header, monkeypatch
):
    """A mode update uses upsert_agent_document directly."""
    app, _ = mongo_app
    called = False

    def set_agent_commanded_mode(*_args, **_kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(
        database, "set_agent_commanded_mode", set_agent_commanded_mode
    )

    output = app.post(
        "/v2/agents/agent1/data",
        json={"mode": "maintenance"},
        headers=agent_auth_header,
    )

    assert output.status_code == HTTPStatus.OK
    assert not called


def test_agents_post_rejects_admin_credentials(mongo_app):
    """POST /v2/agents/{name}/data is agent-only; admin gets 403."""
    app, mongo = mongo_app
    mongo.agents.insert_one({"name": "agent1", "state": "waiting"})
    admin_header = get_access_token_header("admin-id", ServerRoles.ADMIN)

    output = app.post(
        "/v2/agents/agent1/data",
        json={"mode": "offline"},
        headers=admin_header,
    )

    assert output.status_code == HTTPStatus.FORBIDDEN


def test_agents_post_rejects_manager_credentials(mongo_app):
    """POST /v2/agents/{name}/data is agent-only; manager gets 403."""
    app, mongo = mongo_app
    mongo.agents.insert_one({"name": "agent1", "state": "waiting"})
    manager_header = get_access_token_header("manager-id", ServerRoles.MANAGER)

    output = app.post(
        "/v2/agents/agent1/data",
        json={"mode": "offline"},
        headers=manager_header,
    )

    assert output.status_code == HTTPStatus.FORBIDDEN


def test_agents_post_substate_free_mode_rejects_a_state(
    mongo_app, agent_auth_header
):
    """A mode that has no sub-state cannot be given one."""
    app, _ = mongo_app

    output = app.post(
        "/v2/agents/agent1/data",
        json={"mode": "offline", "state": "waiting"},
        headers=agent_auth_header,
    )

    assert output.status_code == HTTPStatus.BAD_REQUEST


def test_agents_post_substate_free_mode_clears_stored_state(
    mongo_app, agent_auth_header
):
    """Moving to a mode without a sub-state drops the stored sub-state."""
    app, mongo = mongo_app
    mongo.agents.insert_one(
        {
            "name": "agent1",
            "mode": {"value": "online"},
            "state": {"value": "provision"},
        }
    )

    output = app.post(
        "/v2/agents/agent1/data",
        json={"mode": "offline"},
        headers=agent_auth_header,
    )

    assert output.status_code == HTTPStatus.OK
    record = mongo.agents.find_one({"name": "agent1"})
    assert record["mode"]["value"] == "offline"
    assert "state" not in record


# ---------------------------------------------------------------------------
# PATCH /v2/agents/{name}/commanded_mode  — admin-only mode command
# ---------------------------------------------------------------------------


def test_agents_patch_commanded_mode_admin(mongo_app):
    """An admin can command a mode change on an existing agent.
    Commanded mode is stored as nested: {value, changed_at, changed_by,
    comment}.
    """
    app, mongo = mongo_app
    mongo.agents.insert_one({"name": "agent1", "state": "waiting"})
    admin_header = get_access_token_header("admin-id", ServerRoles.ADMIN)

    output = app.patch(
        "/v2/agents/agent1/commanded_mode",
        json={"commanded_mode": "offline"},
        headers=admin_header,
    )

    assert output.status_code == HTTPStatus.NO_CONTENT
    record = mongo.agents.find_one({"name": "agent1"})
    assert record["commanded_mode"]["value"] == "offline"
    assert record["commanded_mode"]["changed_by"] == "admin-id"
    assert record["commanded_mode"]["changed_at"] is not None


def test_agents_patch_commanded_mode_rejects_manager_credentials(mongo_app):
    """A manager cannot command a mode change; only admins can."""
    app, mongo = mongo_app
    mongo.agents.insert_one({"name": "agent1", "state": "waiting"})
    manager_header = get_access_token_header("manager-id", ServerRoles.MANAGER)

    output = app.patch(
        "/v2/agents/agent1/commanded_mode",
        json={"commanded_mode": "offline"},
        headers=manager_header,
    )

    assert output.status_code == HTTPStatus.FORBIDDEN


def test_agents_patch_commanded_mode_rejects_agent_credentials(
    mongo_app, agent_auth_header
):
    """An agent cannot command its own mode via the PATCH endpoint."""
    app, mongo = mongo_app
    mongo.agents.insert_one({"name": "agent1", "state": "waiting"})

    output = app.patch(
        "/v2/agents/agent1/commanded_mode",
        json={"commanded_mode": "offline"},
        headers=agent_auth_header,
    )

    assert output.status_code == HTTPStatus.FORBIDDEN


def test_agents_patch_commanded_mode_missing_agent(mongo_app):
    """PATCH returns 404 for an unknown agent; does not create a record."""
    app, mongo = mongo_app
    admin_header = get_access_token_header("admin-id", ServerRoles.ADMIN)

    output = app.patch(
        "/v2/agents/nonexistent/commanded_mode",
        json={"commanded_mode": "offline"},
        headers=admin_header,
    )

    assert output.status_code == HTTPStatus.NOT_FOUND
    assert mongo.agents.find_one({"name": "nonexistent"}) is None


def test_agents_patch_empty_comment_clears_existing_comment(mongo_app):
    """An explicitly empty comment clears the stored comment.
    Comment is stored within the nested commanded_mode document.
    """
    app, mongo = mongo_app
    agent_name = "agent1"
    mongo.agents.insert_one(
        {
            "name": agent_name,
            "commanded_mode": {
                "value": "maintenance",
                "comment": "repair",
            },
        }
    )
    admin_header = get_access_token_header("admin-id", ServerRoles.ADMIN)

    output = app.patch(
        f"/v2/agents/{agent_name}/commanded_mode",
        json={"commanded_mode": "online", "comment": ""},
        headers=admin_header,
    )

    assert output.status_code == HTTPStatus.NO_CONTENT
    assert (
        mongo.agents.find_one({"name": agent_name})["commanded_mode"][
            "comment"
        ]
        == ""
    )


def test_agents_patch_omitted_comment_clears_existing_comment(mongo_app):
    """A PATCH with no comment field clears any existing comment.
    Comment is stored within the nested commanded_mode document.
    """
    app, mongo = mongo_app
    agent_name = "agent1"
    mongo.agents.insert_one(
        {
            "name": agent_name,
            "commanded_mode": {
                "value": "maintenance",
                "comment": "repair",
            },
        }
    )
    admin_header = get_access_token_header("admin-id", ServerRoles.ADMIN)

    output = app.patch(
        f"/v2/agents/{agent_name}/commanded_mode",
        json={"commanded_mode": "online"},
        headers=admin_header,
    )

    assert output.status_code == HTTPStatus.NO_CONTENT
    assert (
        mongo.agents.find_one({"name": agent_name})["commanded_mode"][
            "comment"
        ]
        == ""
    )


def test_agents_patch_unchanged_commanded_mode_not_restamped(mongo_app):
    """Re-patching the same commanded_mode does not update its timestamp.
    Metadata (changed_at, changed_by) is preserved in nested commanded_mode.
    """
    app, mongo = mongo_app
    agent_name = "agent1"
    original_timestamp = time.time()
    mongo.agents.insert_one(
        {
            "name": agent_name,
            "commanded_mode": {
                "value": "offline",
                "changed_by": "someone",
                "changed_at": original_timestamp,
            },
        }
    )
    admin_header = get_access_token_header("admin-id", ServerRoles.ADMIN)

    output = app.patch(
        f"/v2/agents/{agent_name}/commanded_mode",
        json={"commanded_mode": "offline"},
        headers=admin_header,
    )

    assert output.status_code == HTTPStatus.NO_CONTENT
    record = mongo.agents.find_one({"name": agent_name})
    assert record["commanded_mode"]["value"] == "offline"
    assert record["commanded_mode"]["changed_by"] == "someone"
    # Timestamp should be preserved since mode didn't change
    assert record["commanded_mode"]["changed_at"] == original_timestamp


def test_agents_patch_commanded_mode_required(mongo_app):
    """PATCH returns 422 when commanded_mode is absent from the body."""
    app, _ = mongo_app
    admin_header = get_access_token_header("admin-id", ServerRoles.ADMIN)

    output = app.patch(
        "/v2/agents/agent1/commanded_mode",
        json={"comment": "no mode supplied"},
        headers=admin_header,
    )

    assert output.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


# ---------------------------------------------------------------------------
# GET /v2/agents/{name}/data  and  GET /v2/agents/data
# ---------------------------------------------------------------------------


def test_agents_get_one_exposes_the_canonical_shape(
    mongo_app, agent_auth_header
):
    """v2 reports mode and sub-state as separate fields."""
    app, mongo = mongo_app
    mongo.agents.insert_one(
        {
            "name": "agent1",
            "mode": {"value": "maintenance"},
            "state": {"value": "waiting"},
        }
    )

    output = app.get("/v2/agents/agent1/data", headers=agent_auth_header)

    assert output.status_code == HTTPStatus.OK
    assert output.json["mode"]["value"] == "maintenance"
    assert output.json["state"]["value"] == "waiting"


def test_agents_get_one_missing_agent(mongo_app, agent_auth_header):
    """An unknown agent is reported as not found."""
    app, _ = mongo_app

    output = app.get("/v2/agents/nonexistent/data", headers=agent_auth_header)

    assert output.status_code == HTTPStatus.NOT_FOUND


def test_agents_get_all_gives_mode_to_records_written_before_modes(
    mongo_app,
):
    """A record predating modes is reported with a mode inferred from state."""
    app, mongo = mongo_app
    mongo.agents.insert_one({"name": "agent1", "state": "provision"})
    mongo.agents.insert_one({"name": "agent2", "state": "offline"})
    admin_header = get_access_token_header("admin-id", ServerRoles.ADMIN)

    output = app.get("/v2/agents/data", headers=admin_header)

    assert output.status_code == HTTPStatus.OK
    modes = {agent["name"]: agent["mode"]["value"] for agent in output.json}
    assert modes == {"agent1": "online", "agent2": "offline"}


def test_agents_get_one_legacy_offline_has_no_state(
    mongo_app, agent_auth_header
):
    """Legacy offline record has no state in v2 API response."""
    app, mongo = mongo_app
    mongo.agents.insert_one({"name": "agent1", "state": "offline"})

    output = app.get("/v2/agents/agent1/data", headers=agent_auth_header)

    assert output.status_code == HTTPStatus.OK
    data = output.get_json()
    assert data.get("mode")["value"] == "offline"
    assert "state" not in data or data.get("state") is None


def test_agents_get_one_legacy_maintenance_has_waiting_state(
    mongo_app, agent_auth_header
):
    """GET /v2/agents/{name}/data returns state='waiting' for a legacy
    maintenance record.
    """
    app, mongo = mongo_app
    mongo.agents.insert_one({"name": "agent1", "state": "maintenance"})

    output = app.get("/v2/agents/agent1/data", headers=agent_auth_header)

    assert output.status_code == HTTPStatus.OK
    data = output.get_json()
    assert data.get("mode")["value"] == "maintenance"
    assert data.get("state")["value"] == "waiting"


def test_agents_post_patch_post_sequence_preserves_commanded_mode(
    mongo_app, agent_auth_header
):
    """POST-PATCH-POST sequence: admin commanded_mode is preserved.

    Verifies that when an admin issues a PATCH to set commanded_mode,
    a subsequent agent POST does not clobber the commanded_mode field.

    Sequence:
    1. Agent POSTs mode='online', state='waiting'
    2. Admin PATCHes commanded_mode='offline'
    3. Agent POSTs again with mode='online', state='provision'
    4. Verify commanded_mode='offline' is still in DB and visible in response
    """
    app, mongo = mongo_app
    agent_name = "agent1"
    admin_header = get_access_token_header("admin-id", ServerRoles.ADMIN)

    # Step 1: Agent POSTs initial heartbeat
    response = app.post(
        f"/v2/agents/{agent_name}/data",
        json={"mode": "online", "state": "waiting"},
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK
    record = mongo.agents.find_one({"name": agent_name})
    assert record["mode"]["value"] == "online"
    assert record["state"]["value"] == "waiting"
    assert "commanded_mode" not in record

    # Step 2: Admin PATCHes commanded_mode
    response = app.patch(
        f"/v2/agents/{agent_name}/commanded_mode",
        json={"commanded_mode": "offline", "comment": "under maintenance"},
        headers=admin_header,
    )
    assert response.status_code == HTTPStatus.NO_CONTENT
    record = mongo.agents.find_one({"name": agent_name})
    assert record["commanded_mode"]["value"] == "offline"
    assert record["commanded_mode"]["comment"] == "under maintenance"
    # Agent-reported mode should still be present
    assert record["mode"]["value"] == "online"

    # Step 3: Agent POSTs again with different state
    response = app.post(
        f"/v2/agents/{agent_name}/data",
        json={"mode": "online", "state": "provision"},
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK

    # Step 4: Verify commanded_mode is preserved and visible
    record = mongo.agents.find_one({"name": agent_name})
    assert record["commanded_mode"]["value"] == "offline", (
        "Admin-commanded mode should be preserved after agent POST"
    )
    assert record["commanded_mode"]["comment"] == "under maintenance"
    # Agent-reported state should be updated
    assert record["state"]["value"] == "provision"
    # Agent-reported mode should still be online (agent is reporting)
    assert record["mode"]["value"] == "online"

    # Verify v2 GET response shows both fields
    response = app.get(
        f"/v2/agents/{agent_name}/data",
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK
    data = response.get_json()
    assert data["commanded_mode"]["value"] == "offline"
    assert data["mode"]["value"] == "online"
    assert data["state"]["value"] == "provision"


def test_agents_post_matching_mode_clears_commanded_mode(
    mongo_app, agent_auth_header
):
    """When agent reports mode matching commanded_mode, clear commanded_mode.

    Scenario: Agent initiated a restart, posted mode="restart" and exited.
    Server has commanded_mode="restart" (never cleared). Agent restarts and
    on next poll reads commanded_mode="restart" again, causing an infinite
    restart loop.

    This test verifies that when agent POSTs a mode matching the existing
    commanded_mode, the server clears the commanded_mode to prevent
    re-execution.

    Sequence:
    1. Agent POSTs initial heartbeat to create record
    2. Admin PATCHes commanded_mode='restart'
    3. Agent POSTs mode='restart' (agent acts on the command)
    4. Verify commanded_mode is cleared from the database
    5. Next agent restart won't see the stale commanded_mode
    """
    app, mongo = mongo_app
    agent_name = "agent1"
    admin_header = get_access_token_header("admin-id", ServerRoles.ADMIN)

    # Step 1: Agent POSTs initial heartbeat to create the record
    response = app.post(
        f"/v2/agents/{agent_name}/data",
        json={"mode": "online", "state": "waiting"},
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK

    # Step 2: Admin commands restart
    response = app.patch(
        f"/v2/agents/{agent_name}/commanded_mode",
        json={"commanded_mode": "restart", "comment": "update required"},
        headers=admin_header,
    )
    assert response.status_code == HTTPStatus.NO_CONTENT
    record = mongo.agents.find_one({"name": agent_name})
    assert record["commanded_mode"]["value"] == "restart"

    # Step 3: Agent reports it's restarting (acted on the command)
    response = app.post(
        f"/v2/agents/{agent_name}/data",
        json={"mode": "restart"},
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK

    # Step 4: Verify commanded_mode is cleared
    record = mongo.agents.find_one({"name": agent_name})
    assert record["mode"]["value"] == "restart"
    assert "commanded_mode" not in record, (
        "commanded_mode should be cleared when agent POSTs matching mode "
        "to prevent re-execution after restart"
    )

    # Step 5: Verify GET response does not include stale commanded_mode
    response = app.get(
        f"/v2/agents/{agent_name}/data",
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK
    data = response.get_json()
    assert "commanded_mode" not in data


def test_agents_post_restart_saves_current_mode_to_commanded_mode(
    mongo_app, agent_auth_header
):
    """When agent POSTs mode=RESTART, save current mode to commanded_mode.

    Rationale: Agent startup logic is:
      commanded_mode = read from server
      if commanded_mode:
          adopt commanded_mode
      else:
          adopt mode

    When an agent self-restarts, we save the current mode to commanded_mode
    so the agent knows to return to that mode after restart completes.

    Sequence:
    1. Agent POSTs heartbeat in ONLINE mode
    2. Agent POSTs mode='restart' (self-initiated)
    3. Verify current mode (ONLINE) is saved to commanded_mode
    4. Agent will restart and adopt commanded_mode (ONLINE) on next poll
    """
    app, mongo = mongo_app
    agent_name = "agent1"

    # Step 1: Agent POSTs initial heartbeat in ONLINE mode
    response = app.post(
        f"/v2/agents/{agent_name}/data",
        json={"mode": "online", "state": "test"},
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK
    record = mongo.agents.find_one({"name": agent_name})
    assert record["mode"]["value"] == "online"
    assert record["state"]["value"] == "test"

    # Step 2: Agent POSTs mode='restart' (self-initiated restart)
    response = app.post(
        f"/v2/agents/{agent_name}/data",
        json={"mode": "restart"},
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK

    # Step 3: Verify current mode is saved to commanded_mode
    record = mongo.agents.find_one({"name": agent_name})
    assert record["mode"]["value"] == "restart"
    assert record["commanded_mode"]["value"] == "online", (
        "Current mode should be saved to commanded_mode when agent "
        "self-restarts, so it knows to return to that mode after restart"
    )
    # State should be cleared (restart mode has no sub-state)
    assert "state" not in record

    # Step 4: Verify GET response shows the commanded_mode
    response = app.get(
        f"/v2/agents/{agent_name}/data",
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK
    data = response.get_json()
    assert data["mode"]["value"] == "restart"
    assert data["commanded_mode"]["value"] == "online"
