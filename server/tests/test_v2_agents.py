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

from http import HTTPStatus

from testflinger_common.enums import ServerRoles

from testflinger import database
from tests.utilities import get_access_token_header

# ---------------------------------------------------------------------------
# POST /v2/agents/{name}/data  — agent heartbeat
# ---------------------------------------------------------------------------


def test_agents_post_mode_change_is_timestamped(mongo_app, agent_auth_header):
    """Posting a mode change stamps mode_changed_at (no attribution for agent
    reports).
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
    assert record["mode"] == "offline"
    assert "mode_changed_by" not in record
    assert record["mode_changed_at"] is not None


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
        {"name": "agent1", "mode": "online", "state": "provision"}
    )

    output = app.post(
        "/v2/agents/agent1/data",
        json={"mode": "offline"},
        headers=agent_auth_header,
    )

    assert output.status_code == HTTPStatus.OK
    record = mongo.agents.find_one({"name": "agent1"})
    assert record["mode"] == "offline"
    assert "state" not in record


# ---------------------------------------------------------------------------
# PATCH /v2/agents/{name}/commanded_mode  — admin-only mode command
# ---------------------------------------------------------------------------


def test_agents_patch_commanded_mode_admin(mongo_app):
    """An admin can command a mode change on an existing agent."""
    app, mongo = mongo_app
    mongo.agents.insert_one({"name": "agent1", "state": "waiting"})
    admin_header = get_access_token_header("admin-id", ServerRoles.ADMIN)

    output = app.patch(
        "/v2/agents/agent1/commanded_mode",
        json={"commanded_mode": "offline"},
        headers=admin_header,
    )

    assert output.status_code == HTTPStatus.OK
    assert (
        mongo.agents.find_one({"name": "agent1"})["commanded_mode"]
        == "offline"
    )


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
    """An explicitly empty comment clears the stored comment."""
    app, mongo = mongo_app
    agent_name = "agent1"
    mongo.agents.insert_one(
        {
            "name": agent_name,
            "commanded_mode": "maintenance",
            "comment": "repair",
        }
    )
    admin_header = get_access_token_header("admin-id", ServerRoles.ADMIN)

    output = app.patch(
        f"/v2/agents/{agent_name}/commanded_mode",
        json={"commanded_mode": "online", "comment": ""},
        headers=admin_header,
    )

    assert output.status_code == HTTPStatus.OK
    assert mongo.agents.find_one({"name": agent_name})["comment"] == ""


def test_agents_patch_omitted_comment_clears_existing_comment(mongo_app):
    """A PATCH with no comment field clears any existing comment."""
    app, mongo = mongo_app
    agent_name = "agent1"
    mongo.agents.insert_one(
        {
            "name": agent_name,
            "commanded_mode": "maintenance",
            "comment": "repair",
        }
    )
    admin_header = get_access_token_header("admin-id", ServerRoles.ADMIN)

    output = app.patch(
        f"/v2/agents/{agent_name}/commanded_mode",
        json={"commanded_mode": "online"},
        headers=admin_header,
    )

    assert output.status_code == HTTPStatus.OK
    assert mongo.agents.find_one({"name": agent_name})["comment"] == ""


def test_agents_patch_unchanged_commanded_mode_not_restamped(mongo_app):
    """Re-patching the same commanded_mode does not update its timestamp."""
    app, mongo = mongo_app
    agent_name = "agent1"
    mongo.agents.insert_one(
        {
            "name": agent_name,
            "commanded_mode": "offline",
            "commanded_mode_changed_by": "someone",
        }
    )
    admin_header = get_access_token_header("admin-id", ServerRoles.ADMIN)

    output = app.patch(
        f"/v2/agents/{agent_name}/commanded_mode",
        json={"commanded_mode": "offline"},
        headers=admin_header,
    )

    assert output.status_code == HTTPStatus.OK
    record = mongo.agents.find_one({"name": agent_name})
    assert record["commanded_mode"] == "offline"
    assert record["commanded_mode_changed_by"] == "someone"


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
        {"name": "agent1", "mode": "maintenance", "state": "waiting"}
    )

    output = app.get("/v2/agents/agent1/data", headers=agent_auth_header)

    assert output.status_code == HTTPStatus.OK
    assert output.json["mode"] == "maintenance"
    assert output.json["state"] == "waiting"


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
    modes = {agent["name"]: agent["mode"] for agent in output.json}
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
    assert data.get("mode") == "offline"
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
    assert data.get("mode") == "maintenance"
    assert data.get("state") == "waiting"
