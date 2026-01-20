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

from unittest.mock import Mock, patch

import pytest
from ops import testing

from charm import TESTFLINGER_ADMIN_ID, TestflingerCharm

TESFLINGER_CONTAINER = "testflinger"
MONGO_DB_REMOTE_DATA = {
    "endpoints": "mongodb:27017",
    "username": "testflinger",
    "password": "testflinger",
    "database": "testflinger_db",
    "uris": "mongodb://testflinger:testflinger@mongodb:27017/testflinger_db",
}


@pytest.fixture
def ctx() -> testing.Context:
    """Fixture for Charm context."""
    return testing.Context(TestflingerCharm)


def test_missing_mongodb_relation(ctx):
    """Test the charm is waiting a mongodb_client relation."""
    container = testing.Container(name=TESFLINGER_CONTAINER, can_connect=False)
    state_in = testing.State(
        containers=[container],
        leader=True,
    )

    # Charm raises SystemExit when no relation data is present
    with pytest.raises(SystemExit):
        state_out = ctx.run(ctx.on.pebble_ready(container=container), state_in)
        assert state_out.unit_status == testing.WaitingStatus(
            "Waiting for database relation"
        )


def test_mongodb_relation_established(ctx):
    """Test charm is active when the mongodb_client_relation is established."""
    container = testing.Container(name=TESFLINGER_CONTAINER, can_connect=True)
    relation = testing.Relation(
        endpoint="mongodb_client",
        remote_app_name="mongodb",
        remote_app_data=MONGO_DB_REMOTE_DATA,
    )
    state_in = testing.State(
        containers=[container], leader=True, relations=[relation]
    )

    # Validate unit is Active when relation is established
    state_out = ctx.run(ctx.on.relation_changed(relation=relation), state_in)
    assert state_out.unit_status == testing.ActiveStatus()


def test_mongodb_relation_removed(ctx):
    """Test charm status is Waiting if mongodb relation removed."""
    container = testing.Container(name=TESFLINGER_CONTAINER, can_connect=True)
    relation = testing.Relation(
        endpoint="mongodb_client",
        remote_app_name="mongodb",
        remote_app_data=MONGO_DB_REMOTE_DATA,
    )
    # Test that breaking the relation sets WaitingStatus
    state_in = testing.State(
        containers=[container], leader=True, relations=[relation]
    )

    # Charm raises SystemExit when relation is removed
    with pytest.raises(SystemExit):
        state_out = ctx.run(
            ctx.on.relation_broken(relation=relation), state_in
        )
        assert state_out.unit_status == testing.WaitingStatus(
            "Waiting for database relation"
        )


def test_waiting_status_on_container_not_ready(ctx):
    """Status should be waiting when container is not ready."""
    container = testing.Container(name=TESFLINGER_CONTAINER, can_connect=False)
    relation = testing.Relation(
        endpoint="mongodb_client",
        remote_app_name="mongodb",
        remote_app_data=MONGO_DB_REMOTE_DATA,
    )
    state_in = testing.State(
        containers=[container], leader=True, relations=[relation]
    )

    # Validate unit is Waiting when container is not ready
    state_out = ctx.run(ctx.on.config_changed(), state_in)
    assert state_out.unit_status == testing.WaitingStatus(
        "Waiting for Pebble in workload container"
    )


def test_exit_on_empty_relation_data(ctx):
    """Test charm exits on container ready but no relation data."""
    container = testing.Container(name=TESFLINGER_CONTAINER, can_connect=True)
    # Set up a relation with empty data
    relation = testing.Relation(
        endpoint="mongodb_client",
        remote_app_name="mongodb",
        remote_app_data={},
    )
    state_in = testing.State(
        containers=[container], leader=True, relations=[relation]
    )

    # Charm raises SystemExit when relation data is missing
    with pytest.raises(SystemExit):
        ctx.run(ctx.on.config_changed(), state_in)


@patch.object(TestflingerCharm, "connect_to_mongodb")
def test_set_admin_password_creates_new_user(mock_connect, ctx):
    """Test that the admin password action creates a new admin user."""
    # Mock MongoDB connection and collection
    mock_db = Mock()
    mock_collection = Mock()
    mock_db.client_permissions = mock_collection
    mock_collection.count_documents.return_value = 0  # No existing user
    mock_connect.return_value = mock_db

    container = testing.Container(name=TESFLINGER_CONTAINER, can_connect=True)
    relation = testing.Relation(
        endpoint="mongodb_client",
        remote_app_name="mongodb",
        remote_app_data=MONGO_DB_REMOTE_DATA,
    )
    state_in = testing.State(
        containers=[container], leader=True, relations=[relation]
    )

    # Run the set-admin-password action with password parameter
    ctx.run(
        ctx.on.action(
            "set-admin-password", params={"password": "test-password"}
        ),
        state_in,
    )

    # Verify action succeeded and new user was created
    assert ctx.action_results == {"result": "Admin user created successfully"}
    mock_collection.insert_one.assert_called_once()

    # Verify user was created in mocked collection
    insert_call = mock_collection.insert_one.call_args[0][0]
    assert insert_call["client_id"] == TESTFLINGER_ADMIN_ID
    assert insert_call["role"] == "admin"
    assert "client_secret_hash" in insert_call


@patch.object(TestflingerCharm, "connect_to_mongodb")
def test_set_admin_password_updates_existing_user(mock_connect, ctx):
    """Test that the admin password action updates an existing admin user."""
    # Mock MongoDB connection and collection
    mock_db = Mock()
    mock_collection = Mock()
    mock_db.client_permissions = mock_collection
    mock_collection.count_documents.return_value = 1  # Existing found
    mock_connect.return_value = mock_db

    container = testing.Container(name=TESFLINGER_CONTAINER, can_connect=True)
    relation = testing.Relation(
        endpoint="mongodb_client",
        remote_app_name="mongodb",
        remote_app_data=MONGO_DB_REMOTE_DATA,
    )
    state_in = testing.State(
        containers=[container], leader=True, relations=[relation]
    )

    # Run the action with password parameter
    ctx.run(
        ctx.on.action(
            "set-admin-password", params={"password": "new-password"}
        ),
        state_in,
    )

    # Verify action succeeded and user was updated
    assert ctx.action_results == {
        "result": "Admin password updated successfully"
    }
    mock_collection.update_one.assert_called_once()

    # Verify user was updated in mocked collection
    update_call = mock_collection.update_one.call_args
    assert update_call[0][0] == {"client_id": TESTFLINGER_ADMIN_ID}
    assert "$set" in update_call[0][1]
    assert "client_secret_hash" in update_call[0][1]["$set"]
