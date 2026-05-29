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

import helpers
import ops
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
    state_out = ctx.run(
        ctx.on.relation_changed(relation=relation, remote_unit="leader"),
        state_in,
    )
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


def test_blocked_status_on_multiple_ingress_providers(ctx):
    """Status should be blocked when both ingress providers are connected."""
    container = testing.Container(name=TESFLINGER_CONTAINER, can_connect=True)
    mongo_relation = testing.Relation(
        endpoint="mongodb_client",
        remote_app_name="mongodb",
        remote_app_data=MONGO_DB_REMOTE_DATA,
    )
    ingress_relation = testing.Relation(
        endpoint="ingress",
        remote_app_name="ingress-configurator",
    )
    nginx_relation = testing.Relation(
        endpoint="nginx-route",
        remote_app_name="nginx-ingress-integrator",
    )
    state_in = testing.State(
        containers=[container],
        leader=True,
        relations=[mongo_relation, ingress_relation, nginx_relation],
    )

    # Validate unit is Blocked when integrating multiple ingress providers
    state_out = ctx.run(
        ctx.on.relation_changed(
            relation=ingress_relation, remote_unit="leader"
        ),
        state_in,
    )
    assert state_out.unit_status == testing.BlockedStatus(
        "Can't use both nginx-route and ingress together."
    )


def test_ingress_ready(ctx):
    """Validate unit status when ingress is ready."""
    container = testing.Container(name=TESFLINGER_CONTAINER, can_connect=True)
    mongo_relation = testing.Relation(
        endpoint="mongodb_client",
        remote_app_name="mongodb",
        remote_app_data=MONGO_DB_REMOTE_DATA,
    )
    ingress_relation = testing.Relation(
        endpoint="ingress",
        remote_app_name="ingress-configurator",
        remote_app_data={"ingress": '{"url": "http://testflinger.local"}'},
    )

    state_in = testing.State(
        containers=[container],
        leader=True,
        relations=[mongo_relation, ingress_relation],
    )

    state_out = ctx.run(
        ctx.on.relation_changed(
            relation=ingress_relation, remote_unit="leader"
        ),
        state_in,
    )
    assert state_out.unit_status == testing.ActiveStatus()


@patch.object(
    TestflingerCharm, "_run_rotation", return_value="Rotation complete."
)
def test_config_changed_rotates_on_master_key_change(
    mock_rotation, ctx, make_state
):
    """Test rotation triggered when master key config changes."""
    old_key = helpers.generate_b64_key()
    new_key = helpers.generate_b64_key()
    state_in = make_state(
        config={"testflinger_secrets_master_key": new_key},
        stored_key=old_key,
    )

    ctx.run(ctx.on.config_changed(), state_in)

    mock_rotation.assert_called_once()
    env_passed = mock_rotation.call_args[0][0]
    assert env_passed["TESTFLINGER_SECRETS_MASTER_KEY"] == old_key
    assert env_passed["TESTFLINGER_SECRETS_NEW_MASTER_KEY"] == new_key


@patch.object(
    TestflingerCharm, "_run_rotation", return_value="Rotation complete."
)
def test_config_changed_no_rotation_on_first_key_set(
    mock_rotation, ctx, make_state
):
    """Test rotation not triggered when master key set for the first time."""
    state_in = make_state(
        config={"testflinger_secrets_master_key": helpers.generate_b64_key()}
    )
    ctx.run(ctx.on.config_changed(), state_in)

    mock_rotation.assert_not_called()


@patch.object(
    TestflingerCharm,
    "_run_rotation",
    side_effect=ops.pebble.ExecError(
        ["rotate_mongo_secrets_key"], 1, "", "error"
    ),
)
def test_config_changed_blocks_on_rotation_failure(_, ctx, make_state):
    """Test BlockedStatus set when key rotation fails on config change."""
    state_in = make_state(
        config={"testflinger_secrets_master_key": helpers.generate_b64_key()},
        stored_key=helpers.generate_b64_key(),
    )

    state_out = ctx.run(ctx.on.config_changed(), state_in)

    assert state_out.unit_status == testing.BlockedStatus(
        "MongoDB CSFLE Master Key rotation failed."
    )


@patch.object(
    TestflingerCharm, "_run_rotation", return_value="Rotation complete."
)
def test_config_changed_no_rotation_on_non_leader(
    mock_rotation, ctx, make_state
):
    """Test rotation not triggered on non-leader units."""
    state_in = make_state(
        config={"testflinger_secrets_master_key": helpers.generate_b64_key()},
        stored_key=helpers.generate_b64_key(),
        leader=False,
    )

    ctx.run(ctx.on.config_changed(), state_in)

    mock_rotation.assert_not_called()


@patch.object(
    TestflingerCharm, "_run_rotation", return_value="Rotation complete."
)
def test_retry_key_rotation_action_success(mock_rotation, ctx, make_state):
    """Test retry-key-rotation using stored old key and config new key."""
    old_key = helpers.generate_b64_key()
    new_key = helpers.generate_b64_key()
    state_in = make_state(
        config={"testflinger_secrets_master_key": new_key},
        stored_key=old_key,
    )

    ctx.run(ctx.on.action("retry-key-rotation"), state_in)

    mock_rotation.assert_called_once()
    env_passed = mock_rotation.call_args[0][0]
    assert env_passed["TESTFLINGER_SECRETS_MASTER_KEY"] == old_key
    assert env_passed["TESTFLINGER_SECRETS_NEW_MASTER_KEY"] == new_key
    assert ctx.action_results == {"result": "Rotation complete."}


def test_retry_key_rotation_action_no_master_key(ctx, make_state):
    """Test retry-key-rotation fails when no master key is configured."""
    state_in = make_state(config={"testflinger_secrets_master_key": ""})
    with pytest.raises(testing.ActionFailed):
        ctx.run(ctx.on.action("retry-key-rotation"), state_in)


def test_retry_key_rotation_action_no_pending_rotation(ctx, make_state):
    """Test retry-key-rotation fails when there is no pending rotation."""
    current_key = helpers.generate_b64_key()
    state_in = make_state(
        config={"testflinger_secrets_master_key": current_key},
        stored_key=current_key,
    )

    with pytest.raises(testing.ActionFailed):
        ctx.run(ctx.on.action("retry-key-rotation"), state_in)


def test_retry_key_rotation_action_container_not_ready(ctx, make_state):
    """Test retry-key-rotation fails when the container is not ready."""
    state_in = make_state(
        config={"testflinger_secrets_master_key": helpers.generate_b64_key()},
        stored_key=helpers.generate_b64_key(),
        can_connect=False,
    )

    with pytest.raises(testing.ActionFailed):
        ctx.run(ctx.on.action("retry-key-rotation"), state_in)


@patch.object(
    TestflingerCharm,
    "_run_rotation",
    side_effect=ops.pebble.ExecError(
        ["rotate_mongo_secrets_key"], 1, "", "connection refused"
    ),
)
def test_retry_key_rotation_action_exec_error(_, ctx, make_state):
    """Test retry-key-rotation fails when rotation script exits non-zero."""
    state_in = make_state(
        config={"testflinger_secrets_master_key": helpers.generate_b64_key()},
        stored_key=helpers.generate_b64_key(),
    )

    with pytest.raises(testing.ActionFailed):
        ctx.run(ctx.on.action("retry-key-rotation"), state_in)


def test_oidc_config_set_on_charm(ctx, make_state):
    """Test charm is active when OIDC config is set and valid."""
    oidc_config = {
        "oidc_client_id": "client-id",
        "oidc_client_secret": "client-secret",
        "oidc_provider_issuer": "https://oidc-provider.local",
        "web_secret_key": "web-secret-key",
    }
    state_in = make_state(config=oidc_config)
    state_out = ctx.run(ctx.on.config_changed(), state_in)
    assert state_out.unit_status == testing.ActiveStatus()


def test_oidc_config_invalid_on_charm(ctx, make_state):
    """Test charm is blocked when OIDC config is invalid."""
    oidc_config = {
        "oidc_client_id": "client-id",
        "oidc_client_secret": "client-secret",
    }
    state_in = make_state(config=oidc_config)

    # Pydantic validation runs in __init__ via load_config(errors="blocked"),
    # which sets BlockedStatus and raises _Abort before the hook handler runs.
    with pytest.raises(testing.errors.UncaughtCharmError):
        _ = ctx.run(ctx.on.config_changed(), state_in)
def test_ingress_ready_with_conflict(ctx):
    """Test ingress_ready blocks when both ingress providers are active."""
    container = testing.Container(name=TESFLINGER_CONTAINER, can_connect=True)
    mongo_relation = testing.Relation(
        endpoint="mongodb_client",
        remote_app_name="mongodb",
        remote_app_data=MONGO_DB_REMOTE_DATA,
    )
    ingress_relation = testing.Relation(
        endpoint="ingress",
        remote_app_name="ingress-configurator",
        remote_app_data={"ingress": '{"url": "http://testflinger.local"}'},
    )
    nginx_relation = testing.Relation(
        endpoint="nginx-route",
        remote_app_name="nginx-ingress-integrator",
    )
    state_in = testing.State(
        containers=[container],
        leader=True,
        relations=[mongo_relation, ingress_relation, nginx_relation],
    )

    state_out = ctx.run(
        ctx.on.relation_changed(
            relation=ingress_relation, remote_unit="leader"
        ),
        state_in,
    )
    assert state_out.unit_status == testing.BlockedStatus(
        "Can't use both nginx-route and ingress together."
    )


def test_ingress_revoked(ctx):
    """Status should return to active when ingress relation is removed."""
    container = testing.Container(name=TESFLINGER_CONTAINER, can_connect=True)
    mongo_relation = testing.Relation(
        endpoint="mongodb_client",
        remote_app_name="mongodb",
        remote_app_data=MONGO_DB_REMOTE_DATA,
    )
    ingress_relation = testing.Relation(
        endpoint="ingress",
        remote_app_name="ingress-configurator",
    )
    state_in = testing.State(
        containers=[container],
        leader=True,
        relations=[mongo_relation, ingress_relation],
    )

    state_out = ctx.run(
        ctx.on.relation_broken(relation=ingress_relation),
        state_in,
    )
    assert state_out.unit_status == testing.ActiveStatus()


def test_conflict_cleared_on_route_changed(ctx):
    """Blocked status should clear when conflict is resolved."""
    container = testing.Container(name=TESFLINGER_CONTAINER, can_connect=True)
    mongo_relation = testing.Relation(
        endpoint="mongodb_client",
        remote_app_name="mongodb",
        remote_app_data=MONGO_DB_REMOTE_DATA,
    )
    ingress_relation = testing.Relation(
        endpoint="ingress",
        remote_app_name="ingress-configurator",
    )
    state_in = testing.State(
        containers=[container],
        leader=True,
        relations=[mongo_relation, ingress_relation],
        unit_status=testing.BlockedStatus(
            "Can't use both nginx-route and ingress together."
        ),
    )

    state_out = ctx.run(
        ctx.on.relation_changed(
            relation=ingress_relation, remote_unit="leader"
        ),
        state_in,
    )
    assert state_out.unit_status == testing.ActiveStatus()
