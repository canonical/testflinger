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
"""Tests for the v1<->canonical agent translation at the database layer.

The v1 API is unchanged: it speaks only ``state``.  The database
folds v1 writes into the canonical ``mode`` + optional ``state`` shape
on the way in, and v1's ``AgentOut`` schema omits the canonical fields
on the way out.  When v1 is retired, these tests go with it.
"""

from http import HTTPStatus


def test_agents_post_state_is_folded_into_a_mode(mongo_app, agent_auth_header):
    """A v1 state-only update is stored in the canonical mode/state shape."""
    app, mongo = mongo_app
    agent_name = "agent1"

    output = app.post(
        f"/v1/agents/data/{agent_name}",
        json={"state": "provision", "comment": "note only"},
        headers=agent_auth_header,
    )

    assert 200 == output.status_code
    record = mongo.agents.find_one({"name": agent_name})
    assert record["comment"] == "note only"
    assert record["mode"] == "online"
    assert record["state"] == "provision"


def test_agents_post_without_state_preserves_mode(
    mongo_app, agent_auth_header
):
    """A metadata-only v1 update does not reset the commanded mode."""
    app, mongo = mongo_app
    mongo.agents.insert_one(
        {"name": "agent-id", "mode": "maintenance", "state": "waiting"}
    )

    output = app.post(
        "/v1/agents/data/agent-id",
        json={"location": "lab-a"},
        headers=agent_auth_header,
    )

    assert output.status_code == HTTPStatus.OK
    agent = mongo.agents.find_one({"name": "agent-id"})
    assert agent["mode"] == "maintenance"
    assert agent["state"] == "waiting"
    assert agent["location"] == "lab-a"


def test_agents_post_state_does_not_override_commanded_mode(
    mongo_app, agent_auth_header
):
    """A v1 agent reporting state cannot undo a mode set through v2."""
    app, mongo = mongo_app
    mongo.agents.insert_one({"name": "agent-id", "mode": "maintenance"})

    output = app.post(
        "/v1/agents/data/agent-id",
        json={"state": "waiting"},
        headers=agent_auth_header,
    )

    assert output.status_code == HTTPStatus.OK
    agent = mongo.agents.find_one({"name": "agent-id"})
    assert agent["mode"] == "maintenance"
    assert agent["state"] == "waiting"
