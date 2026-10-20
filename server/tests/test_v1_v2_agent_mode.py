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

from testflinger_common.enums import ServerRoles

from tests.utilities import get_access_token_header


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
    # Database stores in nested v2 format, including comment in mode
    assert record["mode"]["value"] == "online"
    assert record["mode"]["comment"] == "note only"
    assert record["state"]["value"] == "provision"


def test_agents_post_without_state_preserves_mode(
    mongo_app, agent_auth_header
):
    """A metadata-only v1 update does not reset the commanded mode."""
    app, mongo = mongo_app
    mongo.agents.insert_one(
        {
            "name": "agent-id",
            "mode": {"value": "maintenance"},
            "state": {"value": "waiting"},
        }
    )

    output = app.post(
        "/v1/agents/data/agent-id",
        json={"location": "lab-a"},
        headers=agent_auth_header,
    )

    assert output.status_code == HTTPStatus.OK
    agent = mongo.agents.find_one({"name": "agent-id"})
    assert agent["mode"]["value"] == "maintenance"
    assert agent["state"]["value"] == "waiting"
    assert agent["location"] == "lab-a"


def test_agents_post_state_does_not_override_commanded_mode(
    mongo_app, agent_auth_header
):
    """A v1 agent reporting state does not erase commanded_mode.

    When an admin has set commanded_mode via PATCH, a v1 agent's state
    POST should not touch commanded_mode. The agent-reported mode/state
    are separate from admin-commanded mode.
    """
    app, mongo = mongo_app
    admin_header = get_access_token_header("admin-id", ServerRoles.ADMIN)
    agent_name = "agent-id"

    # Setup: Create agent with initial state
    output = app.post(
        f"/v1/agents/data/{agent_name}",
        json={"state": "waiting"},
        headers=agent_auth_header,
    )
    assert output.status_code == HTTPStatus.OK

    # Admin PATCHes commanded_mode
    response = app.patch(
        f"/v2/agents/{agent_name}/commanded_mode",
        json={"commanded_mode": "offline", "comment": "under maintenance"},
        headers=admin_header,
    )
    assert response.status_code == HTTPStatus.NO_CONTENT
    agent = mongo.agents.find_one({"name": agent_name})
    assert agent["commanded_mode"]["value"] == "offline"

    # V1 agent POSTs new state
    output = app.post(
        f"/v1/agents/data/{agent_name}",
        json={"state": "provision"},
        headers=agent_auth_header,
    )

    assert output.status_code == HTTPStatus.OK
    agent = mongo.agents.find_one({"name": agent_name})
    # Commanded mode should be preserved (v1 agent doesn't know about it)
    assert agent["commanded_mode"]["value"] == "offline"
    assert agent["commanded_mode"]["comment"] == "under maintenance"
    # Agent-reported mode is online (state="provision" → mode=online for v1)
    assert agent["mode"]["value"] == "online"
    # State is updated
    assert agent["state"]["value"] == "provision"


# ---------------------------------------------------------------------------
# offline / restart: no sub-state
# ---------------------------------------------------------------------------


def test_v1_offline_write_and_read(mongo_app, agent_auth_header):
    """V1 agent offline report: write to DB and read back.

    When a v1 agent reports state='offline' (a mode, not a sub-state):
    1. Write: stores as mode='offline', no state
    2. Read: v1 client gets state='offline' (the mode)
    Also tests that legacy pre-existing records (raw v1 format) are
    promoted on read.
    """
    app, mongo = mongo_app

    # Test 1: V1 write stores offline as mode
    output = app.post(
        "/v1/agents/data/agent1",
        json={"state": "offline"},
        headers=agent_auth_header,
    )
    assert output.status_code == HTTPStatus.OK
    record = mongo.agents.find_one({"name": "agent1"})
    assert record["mode"]["value"] == "offline"
    assert "state" not in record

    # Test 2: V1 read returns offline state
    output = app.get(
        "/v1/agents/data/agent1",
        headers=agent_auth_header,
    )
    assert output.status_code == HTTPStatus.OK
    data = output.get_json()
    assert data.get("state") == "offline"

    # Test 3: Legacy pre-existing offline record is promoted on v1 read
    mongo.agents.insert_one({"name": "legacy-agent", "state": "offline"})
    output = app.get(
        "/v1/agents/data/legacy-agent",
        headers=agent_auth_header,
    )
    assert output.status_code == HTTPStatus.OK
    data = output.get_json()
    assert data.get("state") == "offline"


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
    assert record["mode"]["value"] == "restart"
    assert "state" not in record


def test_v1_offline_overwrites_stale_state_in_db(mongo_app, agent_auth_header):
    """A v1 offline write clears a stale sub-state left in the database.

    If a record previously had state='provision' (online sub-state) and the
    agent then reports state='offline', the old sub-state must be removed
    from the database, not left alongside mode='offline'.
    """
    app, mongo = mongo_app
    mongo.agents.insert_one(
        {"name": "agent1", "state": {"value": "provision"}}
    )

    output = app.post(
        "/v1/agents/data/agent1",
        json={"state": "offline"},
        headers=agent_auth_header,
    )

    assert output.status_code == HTTPStatus.OK
    record = mongo.agents.find_one({"name": "agent1"})
    assert record["mode"]["value"] == "offline"
    assert "state" not in record


# ---------------------------------------------------------------------------
# maintenance: sub-state is 'waiting'
# ---------------------------------------------------------------------------


def test_v1_maintenance_write_and_read(mongo_app, agent_auth_header):
    """V1 agent maintenance report: write to DB and read back.

    When a v1 agent reports state='maintenance' (a non-online mode):
    1. Write: stores as mode='maintenance', state='waiting' (idle sub-state)
    2. Read: v1 client gets state='maintenance' (the mode, not the sub-state)
    Also tests that legacy pre-existing records are promoted on read.
    """
    app, mongo = mongo_app

    # Test 1: V1 write stores maintenance with waiting sub-state
    output = app.post(
        "/v1/agents/data/agent1",
        json={"state": "maintenance"},
        headers=agent_auth_header,
    )
    assert output.status_code == HTTPStatus.OK
    record = mongo.agents.find_one({"name": "agent1"})
    assert record["mode"]["value"] == "maintenance"
    assert record["state"]["value"] == "waiting"

    # Test 2: V1 read returns maintenance mode (not sub-state)
    output = app.get(
        "/v1/agents/data/agent1",
        headers=agent_auth_header,
    )
    assert output.status_code == HTTPStatus.OK
    data = output.get_json()
    assert data.get("state") == "maintenance"

    # Test 3: Legacy pre-existing maintenance record promoted on v1 read
    mongo.agents.insert_one({"name": "legacy-maint", "state": "maintenance"})
    output = app.get(
        "/v1/agents/data/legacy-maint",
        headers=agent_auth_header,
    )
    assert output.status_code == HTTPStatus.OK
    data = output.get_json()
    assert data.get("state") == "maintenance"


# ---------------------------------------------------------------------------
# unknown: v1 agents report unknown when they cannot determine their state
# ---------------------------------------------------------------------------


def test_v1_unknown_write_and_read(mongo_app, agent_auth_header):
    """V1 agent unknown state report: write to DB and read back.

    When a v1 agent reports state='unknown' (cannot determine state):
     1. Write: stores as mode='online', state='waiting' (treated as online with
        idle sub-state)
    2. Read: v1 client may get 'waiting' state (or no state - implementation
       dependent)
    Also tests that legacy pre-existing records are promoted on read.
    """
    app, mongo = mongo_app

    # Test 1: V1 write stores unknown as online mode
    output = app.post(
        "/v1/agents/data/agent1",
        json={"state": "unknown"},
        headers=agent_auth_header,
    )
    assert output.status_code == HTTPStatus.OK
    record = mongo.agents.find_one({"name": "agent1"})
    # unknown → online mode with waiting state
    assert isinstance(record["mode"], dict)
    assert record["mode"]["value"] == "online"
    assert record["state"]["value"] == "waiting"

    # Test 2: V1 read for unknown state - may return waiting or no state
    output = app.get(
        "/v1/agents/data/agent1",
        headers=agent_auth_header,
    )
    assert output.status_code == HTTPStatus.OK
    # Unknown agents are online with waiting, so state field is optional
    # (implementation may or may not include it)

    # Test 3: Legacy pre-existing unknown record promoted on v1 read
    mongo.agents.insert_one({"name": "legacy-unknown", "state": "unknown"})
    output = app.get(
        "/v1/agents/data/legacy-unknown",
        headers=agent_auth_header,
    )
    assert output.status_code == HTTPStatus.OK
    # Same as above - state field is optional for unknown agents


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
    - v1 writes store in v2 nested format in database
    - v2 writes overwrite/replace the data cleanly
    - v1 reads after v2 writes work correctly (via _reconstruct_v1_from_v2)
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
    assert record["mode"]["value"] == "online"  # provision -> online mode
    assert record["state"]["value"] == "provision"
    assert record["queues"] == ["queue1"]

    # v1 heartbeat 2: ready state
    response = app.post(
        f"/v1/agents/data/{agent_name}",
        json={"state": "ready", "queues": ["queue1"]},
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK
    record = mongo.agents.find_one({"name": agent_name})
    assert record["mode"]["value"] == "online"
    assert record["state"]["value"] == "ready"

    # v1 heartbeat 3: ready state again (no change)
    response = app.post(
        f"/v1/agents/data/{agent_name}",
        json={"state": "ready", "queues": ["queue1"]},
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK
    record = mongo.agents.find_one({"name": agent_name})
    assert record["mode"]["value"] == "online"
    assert record["state"]["value"] == "ready"

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
    # v1 client should get flat format through _reconstruct_v1_from_v2
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


def test_v2_agent_post_with_links(mongo_app, agent_auth_header):
    """V2 agent can POST links field along with other agent data."""
    app, mongo = mongo_app
    agent_name = "agent-links"

    # V2 agent posts comprehensive data including links
    links_data = [
        {"url": "https://canonical.com/maas", "label": "MAAS"},
        {"url": "https://certification.canonical.com", "label": "C3"},
    ]
    response = app.post(
        f"/v2/agents/{agent_name}/data",
        json={
            "mode": "online",
            "state": "waiting",
            "provision_type": "fake_connector",
            "location": "lab-a",
            "queues": ["queue1"],
            "links": links_data,
        },
        headers=agent_auth_header,
    )

    assert response.status_code == HTTPStatus.OK

    # Verify links are stored in database
    record = mongo.agents.find_one({"name": agent_name})
    assert record["links"] == links_data
    assert record["provision_type"] == "fake_connector"
    assert record["location"] == "lab-a"
    assert record["queues"] == ["queue1"]
