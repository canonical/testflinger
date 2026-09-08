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


def test_agents_post_mode_change_is_timestamped(mongo_app, agent_auth_header):
    """Posting a mode change stamps mode_changed_at and mode_changed_by."""
    app, mongo = mongo_app
    agent_name = "agent1"

    output = app.post(
        f"/v2/agents/{agent_name}/data",
        json={"mode": "offline", "comment": "downtime"},
        headers=agent_auth_header,
    )

    assert HTTPStatus.OK == output.status_code
    record = mongo.agents.find_one({"name": agent_name})
    assert record["mode"] == "offline"
    assert record["comment"] == "downtime"
    assert record["mode_changed_by"] == "agent-id"
    assert record["mode_changed_at"] is not None


def test_agents_post_writes_mode_with_agent_document(
    mongo_app, agent_auth_header, monkeypatch
):
    """A mode update uses the single agent-document write path."""
    app, _ = mongo_app
    called = False

    def set_agent_mode(*_args, **_kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(database, "set_agent_mode", set_agent_mode)

    output = app.post(
        "/v2/agents/agent1/data",
        json={"mode": "maintenance", "comment": "repair"},
        headers=agent_auth_header,
    )

    assert output.status_code == HTTPStatus.OK
    assert not called


def test_agents_post_admin_cannot_create_agent(mongo_app):
    """Only an agent registration POST may create a new agent record."""
    app, _ = mongo_app
    admin_header = get_access_token_header("admin-id", ServerRoles.ADMIN)

    output = app.post(
        "/v2/agents/new-agent/data",
        json={"mode": "offline"},
        headers=admin_header,
    )

    assert output.status_code == HTTPStatus.NOT_FOUND


def test_agents_post_admin_updates_existing_agent(mongo_app):
    """An administrator can change mode on an existing agent record."""
    app, mongo = mongo_app
    mongo.agents.insert_one({"name": "agent1", "state": "waiting"})
    admin_header = get_access_token_header("admin-id", ServerRoles.ADMIN)

    output = app.post(
        "/v2/agents/agent1/data",
        json={"mode": "offline"},
        headers=admin_header,
    )

    assert output.status_code == HTTPStatus.OK
    assert mongo.agents.find_one({"name": "agent1"})["mode"] == "offline"


def test_agents_post_admin_does_not_recreate_deleted_agent(
    mongo_app, monkeypatch
):
    """An admin mode update cannot recreate an agent deleted after lookup."""
    app, mongo = mongo_app
    mongo.agents.insert_one({"name": "agent1", "state": "waiting"})
    admin_header = get_access_token_header("admin-id", ServerRoles.ADMIN)
    original_upsert_agent_document = database.upsert_agent_document

    def delete_before_agent_write(*args, **kwargs):
        mongo.agents.delete_one({"name": "agent1"})
        return original_upsert_agent_document(*args, **kwargs)

    monkeypatch.setattr(
        database, "upsert_agent_document", delete_before_agent_write
    )

    output = app.post(
        "/v2/agents/agent1/data",
        json={"mode": "offline"},
        headers=admin_header,
    )

    assert output.status_code == HTTPStatus.OK
    assert mongo.agents.find_one({"name": "agent1"}) is None


def test_agents_post_manager_updates_existing_agent(mongo_app):
    """A manager can change mode on an existing agent record."""
    app, mongo = mongo_app
    mongo.agents.insert_one({"name": "agent1", "state": "waiting"})
    manager_header = get_access_token_header("manager-id", ServerRoles.MANAGER)

    output = app.post(
        "/v2/agents/agent1/data",
        json={"mode": "offline"},
        headers=manager_header,
    )

    assert output.status_code == HTTPStatus.OK
    assert mongo.agents.find_one({"name": "agent1"})["mode"] == "offline"


def test_agents_post_empty_comment_clears_existing_comment(
    mongo_app, agent_auth_header
):
    """An explicitly empty comment clears the stored comment."""
    app, mongo = mongo_app
    agent_name = "agent1"
    mongo.agents.insert_one(
        {"name": agent_name, "mode": "maintenance", "comment": "repair"}
    )

    output = app.post(
        f"/v2/agents/{agent_name}/data",
        json={"mode": "online", "comment": ""},
        headers=agent_auth_header,
    )

    assert HTTPStatus.OK == output.status_code
    record = mongo.agents.find_one({"name": agent_name})
    assert record["comment"] == ""


def test_agents_post_mode_without_comment_clears_existing_comment(
    mongo_app, agent_auth_header
):
    """A mode update without comment clears the stored comment."""
    app, mongo = mongo_app
    agent_name = "agent1"
    mongo.agents.insert_one(
        {"name": agent_name, "mode": "maintenance", "comment": "repair"}
    )

    output = app.post(
        f"/v2/agents/{agent_name}/data",
        json={"mode": "online"},
        headers=agent_auth_header,
    )

    assert HTTPStatus.OK == output.status_code
    record = mongo.agents.find_one({"name": agent_name})
    assert record["comment"] == ""


def test_agents_post_unchanged_mode_not_restamped(
    mongo_app, agent_auth_header
):
    """Re-posting the same mode does not update mode_changed_by."""
    app, mongo = mongo_app
    agent_name = "agent1"
    mongo.agents.insert_one(
        {"name": agent_name, "mode": "offline", "mode_changed_by": "someone"}
    )

    output = app.post(
        f"/v2/agents/{agent_name}/data",
        json={"mode": "offline"},
        headers=agent_auth_header,
    )

    assert HTTPStatus.OK == output.status_code
    record = mongo.agents.find_one({"name": agent_name})
    assert record["mode"] == "offline"
    assert record["mode_changed_by"] == "someone"


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
