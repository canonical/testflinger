# Copyright 2024 Canonical
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing


from unittest.mock import patch

from ops import testing


def test_blocked_on_no_config_repo(ctx, state_in):
    """Test blocked status when config-repo is not set."""
    state = state_in(config={"config-repo": ""})
    state_out = ctx.run(ctx.on.config_changed(), state=state)
    assert state_out.unit_status == testing.BlockedStatus(
        "config-repo and config-dir must be set"
    )


def test_blocked_on_no_config_dir(ctx, state_in):
    """Test blocked status when config-dir is not set."""
    state = state_in(config={"config-dir": ""})
    state_out = ctx.run(ctx.on.config_changed(), state=state)
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
    state_in,
):
    """Test update_tf_cmd_scripts is called during config_changed."""
    ctx.run(ctx.on.config_changed(), state=state_in())

    mock_update_scripts.assert_called_once()


def test_blocked_on_no_secret(ctx, state_in, caplog):
    """Test blocked status when credentials-secret config is not set."""
    state_out = ctx.run(ctx.on.start(), state=state_in())
    assert state_out.unit_status == testing.BlockedStatus(
        "Invalid credentials secret"
    )
    assert "credentials-secret config not set" in caplog.text


def test_blocked_on_secret_missing_fields(ctx, state_in, caplog):
    """Test blocked status when secret is missing required fields."""
    secret = testing.Secret(
        tracked_content={"client-id": "test-id"},
    )
    state = state_in(
        config={"credentials-secret": secret.id},
        secrets=[secret],
    )

    state_out = ctx.run(ctx.on.start(), state=state)
    assert state_out.unit_status == testing.BlockedStatus(
        "Invalid credentials secret"
    )
    assert "Secret missing required fields" in caplog.text


def test_blocked_on_secret_incorrect_fields(ctx, state_in, caplog):
    """Test blocked status when secret has incorrect fields."""
    # Correct field name are "client-id" and "secret-key"
    secret = testing.Secret(
        tracked_content={"client": "test-id", "secret": "test-secret"},
    )
    state = state_in(
        config={"credentials-secret": secret.id},
        secrets=[secret],
    )

    state_out = ctx.run(ctx.on.start(), state=state)
    assert state_out.unit_status == testing.BlockedStatus(
        "Invalid credentials secret"
    )
    assert "Secret missing required fields" in caplog.text


@patch("testflinger_client.authenticate", return_value=False)
def test_start_blocked_on_authentication_failure(
    mock_authenticate, ctx, state_in, secret
):
    state = state_in(
        config={"credentials-secret": secret.id},
        secrets=[secret],
    )
    state_out = ctx.run(ctx.on.start(), state=state)
    assert state_out.unit_status == testing.BlockedStatus(
        "Authentication with Testflinger server failed"
    )


@patch("testflinger_client.authenticate", return_value=True)
def test_start_active_on_successful_authentication(
    mock_authenticate, ctx, state_in, secret
):
    """Test active status when authentication is successful."""
    state = state_in(
        config={"credentials-secret": secret.id},
        secrets=[secret],
    )
    state_out = ctx.run(ctx.on.start(), state=state)
    assert state_out.unit_status == testing.ActiveStatus()


@patch("testflinger_client.authenticate", return_value=False)
@patch("charm.supervisord.restart_agents")
@patch("charm.supervisord.supervisor_update")
@patch("charm.TestflingerAgentHostCharm.write_supervisor_service_files")
@patch("charm.update_charm_scripts")
@patch("charm.copy_ssh_keys")
@patch("charm.TestflingerAgentHostCharm.update_config_files")
def test_config_changed_blocked_on_authentication_failure(
    mock_update_config,
    mock_copy_ssh,
    mock_update_scripts,
    mock_write_supervisor,
    mock_supervisor_update,
    mock_restart,
    mock_authenticate,
    ctx,
    state_in,
    secret,
):
    state = state_in(
        config={"credentials-secret": secret.id},
        secrets=[secret],
    )
    state_out = ctx.run(ctx.on.config_changed(), state=state)
    assert state_out.unit_status == testing.BlockedStatus(
        "Authentication with Testflinger server failed"
    )


@patch("charm.TestflingerAgentHostCharm._authenticate_with_server")
def test_authentication_triggered_on_secret_change(
    mock_authenticate_with_server, ctx, state_in, secret
):
    """Test that authentication is triggered when secret changes."""
    state = state_in(
        config={"credentials-secret": secret.id},
        secrets=[secret],
    )
    ctx.run(ctx.on.secret_changed(secret), state=state)
    mock_authenticate_with_server.assert_called_once()


@patch("charm.TestflingerAgentHostCharm._authenticate_with_server")
def test_authentication_triggered_on_update_status(
    mock_authenticate_with_server, ctx, state_in
):
    """Test that authentication is triggered on update_status event."""
    ctx.run(ctx.on.update_status(), state=state_in())
    mock_authenticate_with_server.assert_called_once()
