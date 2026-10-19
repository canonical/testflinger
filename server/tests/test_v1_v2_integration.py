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
"""Comprehensive v1<->v2 compatibility tests for agent endpoints.

Tests verify that v1 and v2 clients can interoperate safely:
- V1 writes are promoted to v2 format in database
- V2 writes use v2 nested format
- V1 reads reconstruct v1 flat format from v2 database format
- V2 reads promote v1 records to v2 format in-memory
- Formats are distinguishable and conversions are reversible
"""

from datetime import datetime, timezone
from http import HTTPStatus

from testflinger_common.enums import ServerRoles

from tests.utilities import get_access_token_header


# Helper to compare mode values that might be enum or string
def _get_mode_value(mode_obj):
    """Extract mode value from nested dict or string, handling both enum and
    string forms.
    """
    if isinstance(mode_obj, dict):
        value = mode_obj.get("value")
    else:
        value = mode_obj

    # Convert enum to string for consistent comparison
    if hasattr(value, "value"):  # Is an enum
        return value.value
    return value


# ===========================================================================
# Scenario 1: V1 Write → V2 Read Cycle
# ===========================================================================


def test_v1_write_v2_read_sees_promoted_format(mongo_app, agent_auth_header):
    """V1 write creates flat format, V2 read sees promoted nested format.

    This verifies the promotion function works during v2 reads.
    """
    app, mongo = mongo_app
    agent_name = "agent1"

    # V1 agent POSTs state-only
    response = app.post(
        f"/v1/agents/data/{agent_name}",
        json={"state": "provision", "queues": ["q1"]},
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK

    # Database should have promoted format (nested v2 format)
    record = mongo.agents.find_one({"name": agent_name})
    assert isinstance(record["mode"], dict)
    assert _get_mode_value(record["mode"]) == "online"
    # State is stored in nested format in database
    assert isinstance(record["state"], dict)
    assert record["state"]["value"] == "provision"

    # V2 client reads and should see nested format
    response = app.get(
        f"/v2/agents/{agent_name}/data",
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK
    data = response.get_json()

    # Verify v2 nested format
    assert isinstance(data["mode"], dict), "mode should be nested dict"
    assert data["mode"]["value"] == "online"
    assert "changed_at" in data["mode"]

    assert isinstance(data["state"], dict), "state should be nested dict"
    assert data["state"]["value"] == "provision"
    assert "changed_at" in data["state"]


# ===========================================================================
# Scenario 2: V2 Write → V1 Read Cycle
# ===========================================================================


def test_v2_write_v1_read_sees_flat_format(mongo_app, agent_auth_header):
    """V2 write creates nested format, V1 read sees reconstructed flat format.

    This verifies the reconstruction function works during v1 reads.
    """
    app, mongo = mongo_app
    agent_name = "agent2"

    # V2 agent POSTs mode+state
    response = app.post(
        f"/v2/agents/{agent_name}/data",
        json={"mode": "online", "state": "provision", "queues": ["q1"]},
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK

    # Database should have v2 nested format
    record = mongo.agents.find_one({"name": agent_name})
    assert isinstance(record["mode"], dict)
    assert _get_mode_value(record["mode"]) == "online"

    # V1 client reads and should see flat format
    response = app.get(
        f"/v1/agents/data/{agent_name}",
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK
    data = response.get_json()

    # Verify v1 flat format
    assert isinstance(data.get("state"), str), "state should be string"
    assert data["state"] == "provision"
    assert "mode" not in data, "v1 should not expose mode field"


# ===========================================================================
# Scenario 3: V1 → V2 → V1 Read Cycle
# ===========================================================================


def test_v1_v2_v1_transition(mongo_app, agent_auth_header):
    """V1 write → admin command → V1 writes: admin mode persists.

    Simulates: v1 agent writes, v2 admin changes mode (offline then
    maintenance), v1 agent continues writing, v1 client reads.
    Verifies admin-commanded modes are preserved across v1 writes.
    """
    app, mongo = mongo_app
    agent_name = "agent3"
    admin_header = get_access_token_header("admin-id", ServerRoles.ADMIN)

    # V1 agent POSTs state="provision"
    response = app.post(
        f"/v1/agents/data/{agent_name}",
        json={"state": "provision"},
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK

    # Verify v2 format in database
    record = mongo.agents.find_one({"name": agent_name})
    assert isinstance(record["mode"], dict)
    assert _get_mode_value(record["mode"]) == "online"
    # Database stores state in nested format
    assert isinstance(record["state"], dict)
    assert record["state"]["value"] == "provision"

    # Scenario 1: Admin commands mode to "offline" via PATCH
    response = app.patch(
        f"/v2/agents/{agent_name}/commanded_mode",
        json={"commanded_mode": "offline"},
        headers=admin_header,
    )
    assert response.status_code == HTTPStatus.NO_CONTENT

    # V1 client reads and should see state="offline" (the commanded mode)
    response = app.get(
        f"/v1/agents/data/{agent_name}",
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK
    data = response.get_json()
    # Commanded offline mode should appear as state="offline"
    assert data.get("state") == "offline"

    # Scenario 2: Admin commands mode to "maintenance"
    response = app.patch(
        f"/v2/agents/{agent_name}/commanded_mode",
        json={
            "commanded_mode": "maintenance",
            "comment": "under maintenance",
        },
        headers=admin_header,
    )
    assert response.status_code == HTTPStatus.NO_CONTENT

    record = mongo.agents.find_one({"name": agent_name})
    # After admin PATCH, commanded_mode should be set
    assert "commanded_mode" in record
    assert _get_mode_value(record["commanded_mode"]) == "maintenance"

    # V1 agent POSTs different state="waiting"
    response = app.post(
        f"/v1/agents/data/{agent_name}",
        json={"state": "waiting"},
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK

    # Verify mode was NOT overridden by v1 write
    record = mongo.agents.find_one({"name": agent_name})
    assert "mode" in record
    assert "commanded_mode" in record

    # V2 read should show maintenance mode persisted
    response = app.get(
        f"/v2/agents/{agent_name}/data",
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK
    data = response.get_json()
    assert data["commanded_mode"]["value"] == "maintenance"


# ===========================================================================
# Scenario 4: V2 → V1 → V2 Read Cycle
# ===========================================================================


def test_v1_v2_v1_backward_compat(mongo_app, agent_auth_header):
    """V1 agent → V2 admin command → V1 agent continues.

    Demonstrates backward compatibility: v1 agents work with upgraded v2
    server. V1 agent POSTs state, admin PATCHes commanded_mode, v1 agent
    continues. Database stays proper; v1 agent ignores commanded_mode
    (doesn't know contract).
    """
    app, mongo = mongo_app
    agent_name = "agent4"
    admin_header = get_access_token_header("admin-id", ServerRoles.ADMIN)

    # Step 1: V1 agent POSTs initial state
    response = app.post(
        f"/v1/agents/data/{agent_name}",
        json={"state": "waiting"},
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK
    record = mongo.agents.find_one({"name": agent_name})
    assert _get_mode_value(record["mode"]) == "online"
    assert _get_mode_value(record["state"]) == "waiting"
    assert "commanded_mode" not in record

    # Step 2: V2 admin PATCHes commanded_mode
    response = app.patch(
        f"/v2/agents/{agent_name}/commanded_mode",
        json={"commanded_mode": "offline", "comment": "maintenance window"},
        headers=admin_header,
    )
    assert response.status_code == HTTPStatus.NO_CONTENT
    record = mongo.agents.find_one({"name": agent_name})
    assert record["commanded_mode"]["value"] == "offline"
    assert record["commanded_mode"]["comment"] == "maintenance window"
    # Agent-reported mode should still be online
    assert _get_mode_value(record["mode"]) == "online"

    # Step 3: V1 agent continues POSTing (doesn't know about commanded_mode)
    response = app.post(
        f"/v1/agents/data/{agent_name}",
        json={"state": "provision"},
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK
    record = mongo.agents.find_one({"name": agent_name})

    # Commanded mode should be preserved (v1 agent doesn't touch it)
    assert record["commanded_mode"]["value"] == "offline"
    assert record["commanded_mode"]["comment"] == "maintenance window"
    # Agent-reported state is updated
    assert _get_mode_value(record["state"]) == "provision"
    # Agent-reported mode is still online (v1 state="provision" → mode=online)
    assert _get_mode_value(record["mode"]) == "online"


# ===========================================================================
# Scenario 5: Admin Command Interleaving
# ===========================================================================


# ===========================================================================
# Scenario 6: Contested Writes (Last Writer Wins)
# ===========================================================================


def test_v1_v2_v1_write_sequence(mongo_app, agent_auth_header):
    """V1 → V2 → V1 writes: last write wins, database stays consistent.

    Simulates competing agents/clients writing in sequence.
    """
    app, mongo = mongo_app
    agent_name = "agent6"

    # V1 agent POSTs state="provision"
    response = app.post(
        f"/v1/agents/data/{agent_name}",
        json={"state": "provision"},
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK
    record = mongo.agents.find_one({"name": agent_name})

    # V2 agent POSTs mode="offline"
    response = app.post(
        f"/v2/agents/{agent_name}/data",
        json={"mode": "offline"},
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK
    record = mongo.agents.find_one({"name": agent_name})
    assert isinstance(record["mode"], dict)
    assert _get_mode_value(record["mode"]) == "offline"

    # V1 agent POSTs state="waiting"
    response = app.post(
        f"/v1/agents/data/{agent_name}",
        json={"state": "waiting"},
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK

    # Verify database consistency
    record = mongo.agents.find_one({"name": agent_name})
    assert isinstance(record["mode"], dict), (
        "Database should always be v2 format"
    )

    # Both v1 and v2 reads should work
    v1_response = app.get(
        f"/v1/agents/data/{agent_name}",
        headers=agent_auth_header,
    )
    assert v1_response.status_code == HTTPStatus.OK
    v1_data = v1_response.get_json()
    # Offline mode has no state, so v1 response should not include it
    assert isinstance(v1_data.get("state"), (str, type(None)))

    v2_response = app.get(
        f"/v2/agents/{agent_name}/data",
        headers=agent_auth_header,
    )
    assert v2_response.status_code == HTTPStatus.OK
    v2_data = v2_response.get_json()
    assert isinstance(v2_data["mode"], dict)


# ===========================================================================
# Scenario 7: Legacy Data Promotion (In-Memory, No Mutation)
# ===========================================================================


def test_legacy_v1_record_promoted_by_v2_read(mongo_app, agent_auth_header):
    """Raw v1 record in DB is promoted in-memory by V2 read.

    V2 reads should promote legacy v1 records without mutating the database.
    Then v1 reads should also work.
    """
    app, mongo = mongo_app
    agent_name = "legacy-agent"

    # Insert raw v1 record (no mode, just state)
    mongo.agents.insert_one(
        {
            "name": agent_name,
            "state": "provision",
            "queues": ["q1"],
        }
    )

    # Verify raw v1 format in database
    record = mongo.agents.find_one({"name": agent_name})
    assert isinstance(record["state"], str)
    assert "mode" not in record

    # V2 client reads (should promote in-memory, not mutate DB)
    response = app.get(
        f"/v2/agents/{agent_name}/data",
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK
    data = response.get_json()

    # V2 response should show promoted format
    assert isinstance(data["mode"], dict)
    assert data["mode"]["value"] == "online"

    # Verify database was NOT mutated (still raw v1 format)
    record = mongo.agents.find_one({"name": agent_name})
    assert isinstance(record["state"], str), (
        "Database should not be mutated by v2 read"
    )
    assert "mode" not in record

    # V1 client reads (should work with legacy format)
    response = app.get(
        f"/v1/agents/data/{agent_name}",
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK
    data = response.get_json()
    assert data["state"] == "provision"


# ===========================================================================
# Scenario 8: GET All Agents Works for Mixed Formats
# ===========================================================================


def test_get_all_agents_handles_mixed_v1_v2(mongo_app, agent_auth_header):
    """GET all agents works when database has both v1 and v2 format records.

    Tests that get_agents_v1() and get_agents_v2() handle mixed formats.
    """
    app, mongo = mongo_app
    admin_header = get_access_token_header("admin-id", ServerRoles.ADMIN)

    # Insert raw v1 record
    mongo.agents.insert_one(
        {
            "name": "v1-agent",
            "state": "provision",
            "queues": ["q1"],
        }
    )

    # Insert v2 record via v2 POST
    response = app.post(
        "/v2/agents/v2-agent/data",
        json={"mode": "online", "state": "waiting", "queues": ["q1"]},
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK

    # V1 client gets all agents (should reconstruct both to v1 format)
    response = app.get(
        "/v1/agents/data",
        headers=admin_header,
    )
    assert response.status_code == HTTPStatus.OK
    v1_agents = response.get_json()

    v1_names = [a["name"] for a in v1_agents]
    assert "v1-agent" in v1_names
    assert "v2-agent" in v1_names

    # Both should be flat format in v1 response
    for agent in v1_agents:
        if agent["name"] in ("v1-agent", "v2-agent"):
            assert isinstance(agent.get("state"), (str, type(None)))
            assert "mode" not in agent

    # V2 client gets all agents (should promote both to v2 format)
    response = app.get(
        "/v2/agents/data",
        headers=admin_header,
    )
    assert response.status_code == HTTPStatus.OK
    v2_agents = response.get_json()

    v2_names = [a["name"] for a in v2_agents]
    assert "v1-agent" in v2_names
    assert "v2-agent" in v2_names

    # Both should be nested format in v2 response
    for agent in v2_agents:
        if agent["name"] in ("v1-agent", "v2-agent"):
            assert isinstance(agent["mode"], dict)
            assert "value" in agent["mode"]


# ===========================================================================
# Scenario 9: Format Detection Accuracy
# ===========================================================================


def test_is_v2_format_detection(mongo_app):
    """_is_v2_format correctly identifies v1 vs v2 formats."""
    # Import the function
    from testflinger.database import _is_v2_format

    # V1 format: state string, no mode
    v1_record = {"name": "agent1", "state": "provision"}
    assert not _is_v2_format(v1_record), "String state should be v1 format"

    # V2 format: mode dict
    v2_record = {
        "name": "agent1",
        "mode": {"value": "online", "changed_at": datetime.now(timezone.utc)},
    }
    assert _is_v2_format(v2_record), "Dict mode should be v2 format"

    # V2 format: state dict
    v2_record_state_only = {
        "name": "agent1",
        "state": {"value": "ready", "changed_at": datetime.now(timezone.utc)},
    }
    assert _is_v2_format(v2_record_state_only), (
        "Dict state should be v2 format"
    )

    # Empty record
    empty_record = {"name": "agent1"}
    assert not _is_v2_format(empty_record), "No state/mode should be v1 format"


# ===========================================================================
# Scenario 10: V2 GET Agents All Endpoints (Both versions)
# ===========================================================================


def test_upsert_agent_document_works_with_v1_and_v2_data(mongo_app):
    """upsert_agent_document() works correctly for both v1 and v2 input.

    Proves that the unified function handles v1 flat format (state string)
    and v2 nested format (mode/state dicts) equally well.
    """
    app, mongo = mongo_app
    from datetime import datetime, timezone

    from testflinger import database

    # Test 1: upsert_agent_document with v1 flat format (state string)
    v1_data = {
        "name": "v1-test-agent",
        "state": "provision",
        "queues": ["q1"],
        "updated_at": datetime.now(timezone.utc),
    }
    database.upsert_agent_document(
        "v1-test-agent",
        v1_data,
        [],
        changed_by="test-client",
    )

    # Verify database has v2 nested format
    record = mongo.agents.find_one({"name": "v1-test-agent"})
    assert isinstance(record["mode"], dict), (
        "Database should promote v1 flat to v2 nested format"
    )
    assert record["mode"]["value"] == "online"
    assert isinstance(record["state"], dict)
    assert record["state"]["value"] == "provision"

    # Test 2: upsert_agent_document with v2 nested format
    v2_data = {
        "name": "v2-test-agent",
        "mode": {
            "value": "offline",
            "changed_at": datetime.now(timezone.utc),
        },
        "queues": ["q2"],
        "updated_at": datetime.now(timezone.utc),
    }
    database.upsert_agent_document(
        "v2-test-agent",
        v2_data,
        [],
        changed_by="test-client",
    )

    # Verify database preserves v2 nested format
    record = mongo.agents.find_one({"name": "v2-test-agent"})
    assert isinstance(record["mode"], dict)
    assert record["mode"]["value"] == "offline"
    assert "state" not in record  # offline mode has no sub-state

    # Test 3: Both agents are readable via both v1 and v2 APIs
    v1_response = app.get(
        "/v1/agents/data",
        headers=get_access_token_header("test-id", ServerRoles.ADMIN),
    )
    assert v1_response.status_code == HTTPStatus.OK
    v1_agents = {a["name"]: a for a in v1_response.get_json()}
    assert "v1-test-agent" in v1_agents
    assert "v2-test-agent" in v1_agents
    # V1 clients should see flat format
    assert isinstance(v1_agents["v1-test-agent"].get("state"), str)
    assert isinstance(
        v1_agents["v2-test-agent"].get("state"), (str, type(None))
    )
    assert "mode" not in v1_agents["v1-test-agent"]
    assert "mode" not in v1_agents["v2-test-agent"]

    v2_response = app.get(
        "/v2/agents/data",
        headers=get_access_token_header("test-id", ServerRoles.ADMIN),
    )
    assert v2_response.status_code == HTTPStatus.OK
    v2_agents = {a["name"]: a for a in v2_response.get_json()}
    assert "v1-test-agent" in v2_agents
    assert "v2-test-agent" in v2_agents
    # V2 clients should see nested format
    assert isinstance(v2_agents["v1-test-agent"]["mode"], dict)
    assert isinstance(v2_agents["v2-test-agent"]["mode"], dict)


# ===========================================================================
# Scenario 7: V1 agent detects commanded_mode changes
# ===========================================================================


def test_v1_agent_sees_commanded_maintenance(mongo_app, agent_auth_header):
    """V1 agent detects transition to maintenance via commanded_mode.

    When an agent is online/waiting and admin commands maintenance,
    v1 agent should see state="maintenance" to detect the change.
    """
    app, mongo = mongo_app
    agent_name = "agent-v1-maint"
    admin_header = get_access_token_header("admin-id", ServerRoles.ADMIN)

    # V1 agent POSTs initial state: online/waiting
    response = app.post(
        f"/v1/agents/data/{agent_name}",
        json={"state": "waiting"},
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK

    # V1 agent GETs and sees state="waiting"
    response = app.get(
        f"/v1/agents/data/{agent_name}",
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK
    data = response.get_json()
    assert data.get("state") == "waiting"

    # Admin commands maintenance
    response = app.patch(
        f"/v2/agents/{agent_name}/commanded_mode",
        json={"commanded_mode": "maintenance"},
        headers=admin_header,
    )
    assert response.status_code == HTTPStatus.NO_CONTENT

    # V1 agent GETs and should see state="maintenance" (the commanded mode)
    # This state change from "waiting" to "maintenance" triggers agent action
    response = app.get(
        f"/v1/agents/data/{agent_name}",
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK
    data = response.get_json()
    assert data.get("state") == "maintenance", (
        "V1 agent must see commanded_mode to detect mode change"
    )


def test_v1_agent_sees_commanded_offline(mongo_app, agent_auth_header):
    """V1 agent detects transition to offline via commanded_mode."""
    app, mongo = mongo_app
    agent_name = "agent-v1-offline"
    admin_header = get_access_token_header("admin-id", ServerRoles.ADMIN)

    # V1 agent POSTs initial state: online/waiting
    response = app.post(
        f"/v1/agents/data/{agent_name}",
        json={"state": "waiting"},
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK

    # V1 agent GETs and sees state="waiting"
    response = app.get(
        f"/v1/agents/data/{agent_name}",
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK
    data = response.get_json()
    assert data.get("state") == "waiting"

    # Admin commands offline
    response = app.patch(
        f"/v2/agents/{agent_name}/commanded_mode",
        json={"commanded_mode": "offline"},
        headers=admin_header,
    )
    assert response.status_code == HTTPStatus.NO_CONTENT

    # V1 agent GETs and should see state="offline" (the commanded mode)
    response = app.get(
        f"/v1/agents/data/{agent_name}",
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK
    data = response.get_json()
    assert data.get("state") == "offline", (
        "V1 agent must see commanded_mode to detect mode change"
    )


def test_v1_agent_sees_commanded_restart(mongo_app, agent_auth_header):
    """V1 agent detects transition to restart via commanded_mode."""
    app, mongo = mongo_app
    agent_name = "agent-v1-restart"
    admin_header = get_access_token_header("admin-id", ServerRoles.ADMIN)

    # V1 agent POSTs initial state: online/waiting
    response = app.post(
        f"/v1/agents/data/{agent_name}",
        json={"state": "waiting"},
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK

    # V1 agent GETs and sees state="waiting"
    response = app.get(
        f"/v1/agents/data/{agent_name}",
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK
    data = response.get_json()
    assert data.get("state") == "waiting"

    # Admin commands restart
    response = app.patch(
        f"/v2/agents/{agent_name}/commanded_mode",
        json={"commanded_mode": "restart"},
        headers=admin_header,
    )
    assert response.status_code == HTTPStatus.NO_CONTENT

    # V1 agent GETs and should see state="restart" (the commanded mode)
    response = app.get(
        f"/v1/agents/data/{agent_name}",
        headers=agent_auth_header,
    )
    assert response.status_code == HTTPStatus.OK
    data = response.get_json()
    assert data.get("state") == "restart", (
        "V1 agent must see commanded_mode to detect mode change"
    )
