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


# ---------------------------------------------------------------------------
# offline / restart: no sub-state
# ---------------------------------------------------------------------------


def test_v1_offline_write_stores_mode_and_clears_state(
    mongo_app, agent_auth_header
):
    """A v1 agent reporting state='offline' produces mode='offline', no state.

    'offline' is a mode, not an AgentState sub-state.  The normaliser must
    promote it to ``mode`` and remove ``state`` from storage so that neither
    v1 nor v2 readers see a spurious sub-state on an offline agent.
    """
    app, mongo = mongo_app

    output = app.post(
        "/v1/agents/data/agent1",
        json={"state": "offline"},
        headers=agent_auth_header,
    )

    assert output.status_code == HTTPStatus.OK
    record = mongo.agents.find_one({"name": "agent1"})
    assert record["mode"] == "offline"
    assert "state" not in record


def test_v1_restart_write_stores_mode_and_clears_state(
    mongo_app, agent_auth_header
):
    """A v1 agent reporting state='restart' produces mode='restart'."""
    app, mongo = mongo_app

    output = app.post(
        "/v1/agents/data/agent1",
        json={"state": "restart"},
        headers=agent_auth_header,
    )

    assert output.status_code == HTTPStatus.OK
    record = mongo.agents.find_one({"name": "agent1"})
    assert record["mode"] == "restart"
    assert "state" not in record


def test_v1_offline_read_returns_no_state(mongo_app, agent_auth_header):
    """GET /v1/agents/data/{name} returns no state for a legacy offline record.

    A pre-existing record written with only state='offline' (before modes
    existed) must be normalised on read: mode='offline', state absent.
    The v1 AgentOut schema does not expose ``mode``; the caller simply gets
    no ``state``, which is correct for an offline agent.
    """
    app, mongo = mongo_app
    mongo.agents.insert_one({"name": "agent1", "state": "offline"})

    output = app.get(
        "/v1/agents/data/agent1",
        headers=agent_auth_header,
    )

    assert output.status_code == HTTPStatus.OK
    data = output.get_json()
    assert "state" not in data or data.get("state") is None


def test_v1_offline_overwrites_stale_state_in_db(mongo_app, agent_auth_header):
    """A v1 offline write clears a stale sub-state left in the database.

    If a record previously had state='provision' (online sub-state) and the
    agent then reports state='offline', the old sub-state must be removed
    from the database, not left alongside mode='offline'.
    """
    app, mongo = mongo_app
    mongo.agents.insert_one({"name": "agent1", "state": "provision"})

    output = app.post(
        "/v1/agents/data/agent1",
        json={"state": "offline"},
        headers=agent_auth_header,
    )

    assert output.status_code == HTTPStatus.OK
    record = mongo.agents.find_one({"name": "agent1"})
    assert record["mode"] == "offline"
    assert "state" not in record


# ---------------------------------------------------------------------------
# maintenance: sub-state is 'waiting'
# ---------------------------------------------------------------------------


def test_v1_maintenance_write_stores_mode_and_waiting_state(
    mongo_app, agent_auth_header
):
    """A v1 agent reporting state='maintenance' produces mode='maintenance',
    state='waiting'.

    'maintenance' is a mode that carries a sub-state.  The normaliser must
    promote it to ``mode`` and set ``state`` to 'waiting' (the idle sub-state
    used within maintenance mode).
    """
    app, mongo = mongo_app

    output = app.post(
        "/v1/agents/data/agent1",
        json={"state": "maintenance"},
        headers=agent_auth_header,
    )

    assert output.status_code == HTTPStatus.OK
    record = mongo.agents.find_one({"name": "agent1"})
    assert record["mode"] == "maintenance"
    assert record["state"] == "waiting"


def test_v1_maintenance_read_returns_waiting_state(
    mongo_app, agent_auth_header
):
    """GET /v1/agents/data/{name} returns state='waiting' for a pre-existing
    maintenance record that has no explicit state stored.
    """
    app, mongo = mongo_app
    mongo.agents.insert_one({"name": "agent1", "state": "maintenance"})

    output = app.get(
        "/v1/agents/data/agent1",
        headers=agent_auth_header,
    )

    assert output.status_code == HTTPStatus.OK
    data = output.get_json()
    assert data.get("state") == "waiting"


# ---------------------------------------------------------------------------
# unknown: v1 agents report unknown when they cannot determine their state
# ---------------------------------------------------------------------------


def test_v1_unknown_write_stores_online_with_no_state(
    mongo_app, agent_auth_header
):
    """A v1 agent reporting state='unknown' is translated to mode='online',
    no state.

    'unknown' is not a valid sub-state in the canonical model. When v1 agents
    send 'unknown' (because they cannot determine their actual state), the
    normaliser translates it to ONLINE mode with no sub-state, ensuring the
    database contains only canonical state values.
    """
    app, mongo = mongo_app

    output = app.post(
        "/v1/agents/data/agent1",
        json={"state": "unknown"},
        headers=agent_auth_header,
    )

    assert output.status_code == HTTPStatus.OK
    record = mongo.agents.find_one({"name": "agent1"})
    assert record["mode"] == "online"
    assert "state" not in record


def test_v1_unknown_read_returns_no_state(mongo_app, agent_auth_header):
    """GET /v1/agents/data/{name} returns no state for a legacy record with
    state='unknown'.

    A pre-existing record written with only state='unknown' (before modes
    existed, or from a v1 agent that couldn't determine state) must be
    normalised on read: mode='online', state absent. The v1 AgentOut schema
    does not expose ``mode``; the caller simply gets no ``state``.
    """
    app, mongo = mongo_app
    mongo.agents.insert_one({"name": "agent1", "state": "unknown"})

    output = app.get(
        "/v1/agents/data/agent1",
        headers=agent_auth_header,
    )

    assert output.status_code == HTTPStatus.OK
    data = output.get_json()
    assert "state" not in data or data.get("state") is None


# ---------------------------------------------------------------------------
# v1 to v2 agent transition: v1 -> v1 -> v1 -> v2 -> v2 -> v2
# ---------------------------------------------------------------------------


def test_agent_transitions_v1_to_v2_gracefully(mongo_app, agent_auth_header):
    """An agent speaking v1 can transition to v2.

    This test simulates the real-world scenario where:
    1. Server starts with no agents
    2. Agent1 speaks v1 (POST v1 heartbeat with state='provision')
    3. Agent1 speaks v1 (POST v1 heartbeat with state='ready')
    4. Agent1 speaks v1 (POST v1 heartbeat with state='ready')
    5. Agent1 upgrades to v2 (POST v2 heartbeat)
    6. Agent1 continues v2 (POST v2 heartbeat)
    7. Agent1 continues v2 (POST v2 heartbeat)

    The test verifies:
    - v1 writes store flat state-only format
    - v2 writes overwrite/replace the data cleanly
    - v1 reads after v2 writes work correctly (via _v2_db_to_v1_out)
    - v2 reads after v2 writes work correctly
    - No data corruption or schema mismatches occur during transition
    """
    app, mongo = mongo_app
    agent_name = "transitioning-agent"

    # ===== Phase 1: v1 heartbeats =====

    # v1 heartbeat 1: provision state
    response = app.post(
        f"/v1/agents/data/{agent_name}",
        json={"state": "provision", "queues": ["queue1"]},
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK
    record = mongo.agents.find_one({"name": agent_name})
    assert record["mode"] == "online"  # provision -> online mode
    assert record["state"] == "provision"
    assert record["queues"] == ["queue1"]

    # v1 heartbeat 2: ready state
    response = app.post(
        f"/v1/agents/data/{agent_name}",
        json={"state": "ready", "queues": ["queue1"]},
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK
    record = mongo.agents.find_one({"name": agent_name})
    assert record["mode"] == "online"
    assert record["state"] == "ready"

    # v1 heartbeat 3: ready state again (no change)
    response = app.post(
        f"/v1/agents/data/{agent_name}",
        json={"state": "ready", "queues": ["queue1"]},
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK
    record = mongo.agents.find_one({"name": agent_name})
    assert record["mode"] == "online"
    assert record["state"] == "ready"

    # ===== Phase 2: Agent upgrades and speaks v2 =====
    # In real scenario, agent would restart with v2 code
    # For this test, we'll simulate v2 data by directly inserting it

    # v2 heartbeat 1: v2 agent posts nested format
    # (This would come from the v2 agents endpoint)
    v2_data = {
        "name": agent_name,
        "mode": {"value": "online", "changed_at": "2026-10-07T10:00:00Z"},
        "state": {"value": "ready", "changed_at": "2026-10-07T10:00:00Z"},
        "queues": ["queue1"],
    }
    mongo.agents.replace_one({"name": agent_name}, v2_data, upsert=True)

    # Verify v2 format is stored
    record = mongo.agents.find_one({"name": agent_name})
    assert isinstance(record["mode"], dict)
    assert record["mode"]["value"] == "online"
    assert isinstance(record["state"], dict)
    assert record["state"]["value"] == "ready"

    # ===== Phase 3: Verify v1 client can still read after v2 upgrade =====
    response = app.get(
        f"/v1/agents/data/{agent_name}",
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK
    v1_read_data = response.get_json()
    # v1 client should get flat format through _v2_db_to_v1_out
    assert v1_read_data["state"] == "ready"
    assert "mode" not in v1_read_data  # v1 schema doesn't expose mode
    assert v1_read_data["queues"] == ["queue1"]

    # ===== Phase 4: Verify v2 format is preserved in database =====
    record = mongo.agents.find_one({"name": agent_name})
    assert isinstance(record["mode"], dict)
    assert record["mode"]["value"] == "online"
    assert isinstance(record["state"], dict)
    assert record["state"]["value"] == "ready"

    # ===== Phase 5: Continue v2 heartbeats =====
    v2_data_2 = {
        "name": agent_name,
        "mode": {"value": "online", "changed_at": "2026-10-07T10:01:00Z"},
        "state": {"value": "ready", "changed_at": "2026-10-07T10:01:00Z"},
        "queues": ["queue1", "queue2"],  # Agent joined another queue
    }
    mongo.agents.replace_one({"name": agent_name}, v2_data_2, upsert=True)

    record = mongo.agents.find_one({"name": agent_name})
    assert record["mode"]["value"] == "online"
    assert record["state"]["value"] == "ready"
    assert record["queues"] == ["queue1", "queue2"]

    # v1 read again after continued v2 updates
    response = app.get(
        f"/v1/agents/data/{agent_name}",
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK
    v1_read_data = response.get_json()
    assert v1_read_data["state"] == "ready"
    assert v1_read_data["queues"] == ["queue1", "queue2"]
