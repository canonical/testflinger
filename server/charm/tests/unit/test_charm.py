# Copyright (C) 2023 Canonical
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
"""Unit tests for Testflinger Juju charm."""

from pathlib import Path
from unittest.mock import Mock, patch

import ops
import ops.testing
import pytest

from charm import TESTFLINGER_ADMIN_ID, TestflingerCharm

CHARMDIR = Path(__file__).parent.parent.parent.resolve()


@pytest.fixture(name="harness")
def fixture_harness():
    """Pytest fixture for getting the harness."""
    harness = ops.testing.Harness(TestflingerCharm)
    return harness


def test_waiting_for_relation(harness):
    """Test that the status is set to waiting when relation is not present."""
    harness.begin()
    with pytest.raises(SystemExit):
        assert harness.container_pebble_ready("testflinger")
    assert isinstance(harness.model.unit.status, ops.WaitingStatus)


def test_good_relation_active_status(harness):
    """Status should be active when the relation is present."""
    harness.container_pebble_ready("testflinger")
    harness.set_can_connect("testflinger", True)
    harness.begin()
    rel_id = harness.add_relation("mongodb_client", "mongodb")
    harness.update_relation_data(
        rel_id,
        "mongodb",
        {
            "port": "27017",
            "host": "mongodb",
            "username": "testflinger",
            "password": "testflinger",
            "database": "testflinger_db",
            "endpoints": "mongodb/0",
        },
    )
    assert isinstance(harness.model.unit.status, ops.ActiveStatus)


def test_remove_relation_waiting_status(harness):
    """Status should be waiting when the relation is present."""
    harness.container_pebble_ready("testflinger")
    harness.set_can_connect("testflinger", True)
    harness.begin()
    rel_id = harness.add_relation("mongodb_client", "mongodb")
    harness.update_relation_data(
        rel_id,
        "mongodb",
        {
            "port": "27017",
            "host": "mongodb",
            "username": "testflinger",
            "password": "testflinger",
            "database": "testflinger_db",
            "endpoints": "mongodb/0",
        },
    )
    assert isinstance(harness.model.unit.status, ops.ActiveStatus)
    with pytest.raises(SystemExit):
        harness.remove_relation(rel_id)
    assert isinstance(harness.model.unit.status, ops.WaitingStatus)


def test_container_cant_connect_waiting_status(harness):
    """Status should be waiting container can't connect."""
    harness.container_pebble_ready("testflinger")
    harness.set_can_connect("testflinger", False)
    harness.begin()
    rel_id = harness.add_relation("mongodb_client", "mongodb")
    harness.update_relation_data(
        rel_id,
        "mongodb",
        {
            "port": "27017",
            "host": "mongodb",
            "username": "testflinger",
            "password": "testflinger",
            "database": "testflinger_db",
            "endpoints": "mongodb/0",
        },
    )
    assert isinstance(harness.model.unit.status, ops.WaitingStatus)


def test_incomplete_relation_maintenance_status(harness):
    """Status should be maintenance when relation data is incomplete."""
    harness.container_pebble_ready("testflinger")
    harness.set_can_connect("testflinger", False)
    harness.begin()
    rel_id = harness.add_relation("mongodb_client", "mongodb")
    harness.update_relation_data(
        rel_id,
        "mongodb",
        {
            "port": "27017",
            "host": "mongodb",
        },
    )
    assert isinstance(harness.model.unit.status, ops.MaintenanceStatus)


@patch("charm.MongoClient")
def test_set_admin_password(mock_mongo_client, harness):
    """Test creating a new admin user when one doesn't exist."""
    harness.begin()
    harness.set_leader(True)

    # Mock MongoDB connection
    mock_db = Mock()
    mock_collection = Mock()
    mock_db.client_permissions = mock_collection
    mock_collection.count_documents.return_value = 0  # No existing user

    # Setup relation data
    rel_id = harness.add_relation("mongodb_client", "mongodb")
    harness.update_relation_data(
        rel_id,
        harness.charm.app.name,
        {
            "database": "testflinger_db",
            "uris": "mongodb://testflinger:testflinger@mongo:27017/testflinger_db",
        },
    )

    with patch.object(
        harness.charm, "connect_to_mongodb", return_value=mock_db
    ):
        # Run the action
        action_event = Mock()
        action_event.params = {"password": "test123"}
        harness.charm.on_set_admin_password(action_event)

    # Verify new user was created
    mock_collection.insert_one.assert_called_once()
    insert_call = mock_collection.insert_one.call_args[0][0]
    print(insert_call)
    assert insert_call["client_id"] == TESTFLINGER_ADMIN_ID
    assert insert_call["role"] == "admin"
    assert "client_secret_hash" in insert_call

    action_event.set_results.assert_called_once_with(
        {"result": "Admin user created successfully"}
    )


@patch("charm.MongoClient")
def test_update_admin_password(mock_mongo_client, harness):
    """Test updating an existing admin user's password."""
    harness.begin()
    harness.set_leader(True)

    # Mock MongoDB connection
    mock_db = Mock()
    mock_collection = Mock()
    mock_db.client_permissions = mock_collection
    mock_collection.count_documents.return_value = 1  # Existing user found

    # Setup relation data
    rel_id = harness.add_relation("mongodb_client", "mongodb")
    harness.update_relation_data(
        rel_id,
        harness.charm.app.name,
        {
            "database": "testflinger_db",
            "uris": "mongodb://testflinger:testflinger@mongo:27017/testflinger_db",
        },
    )

    with patch.object(
        harness.charm, "connect_to_mongodb", return_value=mock_db
    ):
        # Run the action
        action_event = Mock()
        action_event.params = {"password": "newpass456"}
        harness.charm.on_set_admin_password(action_event)

    # Verify user was updated
    mock_collection.update_one.assert_called_once()
    update_call = mock_collection.update_one.call_args
    print(update_call)
    assert update_call[0][0] == {"client_id": TESTFLINGER_ADMIN_ID}
    assert "$set" in update_call[0][1]
    assert "client_secret_hash" in update_call[0][1]["$set"]

    action_event.set_results.assert_called_once_with(
        {"result": "Admin password updated successfully"}
    )
