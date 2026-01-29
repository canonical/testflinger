# Copyright 2024 Canonical
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing


from unittest.mock import patch

import pytest
from charm import TestflingerAgentHostCharm
from ops import testing


@pytest.fixture
def ctx() -> testing.Context:
    return testing.Context(TestflingerAgentHostCharm)


def test_blocked_on_no_config_repo(ctx):
    """Test blocked status when config-repo is not set."""
    state_in = testing.State(
        config={
            "config-repo": "",
            "config-dir": "agent-configs",
        }
    )
    state_out = ctx.run(ctx.on.config_changed(), state=state_in)
    assert state_out.unit_status == testing.BlockedStatus(
        "config-repo and config-dir must be set"
    )


def test_blocked_on_no_config_dir(ctx):
    """Test blocked status when config-dir is not set."""
    state_in = testing.State(
        config={
            "config-repo": "some-repo",
            "config-dir": "",
        }
    )
    state_out = ctx.run(ctx.on.config_changed(), state=state_in)
    assert state_out.unit_status == testing.BlockedStatus(
        "config-repo and config-dir must be set"
    )


@patch("charm.update_charm_scripts")
@patch("charm.copy_ssh_keys")
@patch("charm.supervisord.supervisor_update")
@patch("charm.TestflingerAgentHostCharm.write_supervisor_service_files")
@patch("charm.supervisord.restart_agents")
@patch("charm.TestflingerAgentHostCharm.update_config_files")
def test_update_tf_cmd_scripts_on_config_changed(
    mock_update_config,
    mock_restart,
    mock_write_supervisor,
    mock_supervisor_update,
    mock_copy_ssh,
    mock_update_scripts,
    ctx,
):
    """Test update_tf_cmd_scripts is called during config_changed."""
    state_in = testing.State(
        config={
            "config-repo": "some-repo",
            "config-dir": "agent-configs",
        }
    )

    ctx.run(ctx.on.config_changed(), state=state_in)

    mock_update_scripts.assert_called_once()


def test_blocked_on_no_valid_server(ctx):
    """Test blocked status when server is not set."""
    secret = testing.Secret(
        tracked_content={"client_id": "test-id", "secret_key": "test-key"},
        label="testflinger-credentials",
    )
    state_in = testing.State(
        config={
            "config-repo": "some-repo",
            "config-dir": "agent-configs",
            "testflinger-server": "localhost:5000",
        },
        secrets=[secret],
    )
    state_out = ctx.run(ctx.on.start(), state=state_in)
    assert state_out.unit_status == testing.BlockedStatus(
        "Testflinger server config not set or invalid"
    )


def test_blocked_on_no_secret(ctx):
    """Test blocked status when secret is not set."""
    state_in = testing.State(
        config={"config-repo": "some-repo", "config-dir": "agent-configs"}
    )

    state_out = ctx.run(ctx.on.start(), state=state_in)
    assert state_out.unit_status == testing.BlockedStatus(
        "Missing testflinger-credentials secret"
    )


def test_blocked_on_secret_missing_fields(ctx):
    """Test blocked status when secret is missing required fields."""
    secret = testing.Secret(
        tracked_content={"client_id": "test-id"},
        label="testflinger-credentials",
    )
    state_in = testing.State(
        config={
            "config-repo": "some-repo",
            "config-dir": "agent-configs",
        },
        secrets=[secret],
    )

    state_out = ctx.run(ctx.on.start(), state=state_in)
    assert state_out.unit_status == testing.BlockedStatus(
        "Secret missing client_id or secret_key"
    )


def test_blocked_on_secret_incorrect_fields(ctx):
    """Test blocked status when secret has incorrect fields."""
    secret = testing.Secret(
        tracked_content={"client": "test-id", "secret": "test-secret"},
        label="testflinger-credentials",
    )
    state_in = testing.State(
        config={
            "config-repo": "some-repo",
            "config-dir": "agent-configs",
        },
        secrets=[secret],
    )

    state_out = ctx.run(ctx.on.start(), state=state_in)
    assert state_out.unit_status == testing.BlockedStatus(
        "Secret missing client_id or secret_key"
    )


@patch("charm.authenticate", return_value=False)
def test_blocked_on_authentication_failure(mock_authenticate, ctx):
    """Test blocked status when authentication fails."""
    secret = testing.Secret(
        tracked_content={"client_id": "test-id", "secret_key": "test-key"},
        label="testflinger-credentials",
    )
    state_in = testing.State(
        config={
            "config-repo": "some-repo",
            "config-dir": "agent-configs",
        },
        secrets=[secret],
    )
    state_out = ctx.run(ctx.on.start(), state=state_in)
    assert state_out.unit_status == testing.BlockedStatus(
        "Authentication with Testflinger server failed"
    )


@patch("charm.authenticate", return_value=True)
def test_active_on_successful_authentication(mock_authenticate, ctx):
    """Test active status when authentication is successful."""
    secret = testing.Secret(
        tracked_content={"client_id": "test-id", "secret_key": "test-key"},
        label="testflinger-credentials",
    )
    state_in = testing.State(
        config={
            "config-repo": "some-repo",
            "config-dir": "agent-configs",
        },
        secrets=[secret],
    )
    state_out = ctx.run(ctx.on.start(), state=state_in)
    assert state_out.unit_status == testing.ActiveStatus()


@patch("charm.TestflingerAgentHostCharm._authenticate_with_server")
def test_authentication_triggered_on_secret_change(
    mock_authenticate_with_server, ctx
):
    """Test that authentication is triggered when secret changes."""
    secret = testing.Secret(
        tracked_content={"client_id": "test-id", "secret_key": "test-key"},
        label="testflinger-credentials",
    )
    state_in = testing.State(
        config={
            "config-repo": "some-repo",
            "config-dir": "agent-configs",
        },
        secrets=[secret],
    )
    ctx.run(ctx.on.secret_changed(secret), state=state_in)
    mock_authenticate_with_server.assert_called_once()


@patch("charm.TestflingerAgentHostCharm._authenticate_with_server")
def test_authentication_triggered_on_update_status(
    mock_authenticate_with_server, ctx
):
    """Test that authentication is triggered on update_status event."""
    state_in = testing.State(
        config={
            "config-repo": "some-repo",
            "config-dir": "agent-configs",
        },
    )
    ctx.run(ctx.on.update_status(), state=state_in)
    mock_authenticate_with_server.assert_called_once()
