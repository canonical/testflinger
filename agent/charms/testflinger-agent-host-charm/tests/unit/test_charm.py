# Copyright 2024 Canonical
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing


from unittest.mock import patch

import pytest
from ops import testing


def test_blocked_on_no_config_repo(ctx, state_in):
    """Test charm aborts when config-repo is not set."""
    # Pydantic validation runs in __init__ via load_config(errors="blocked"),
    # which sets BlockedStatus and raises _Abort before the hook handler runs.
    state = state_in(config={"config-repo": ""})
    with pytest.raises(testing.errors.UncaughtCharmError):
        ctx.run(ctx.on.config_changed(), state=state)


def test_blocked_on_no_config_dir(ctx, state_in):
    """Test charm aborts when config-dir is not set."""
    # Pydantic validation runs in __init__ via load_config(errors="blocked"),
    # which sets BlockedStatus and raises _Abort before the hook handler runs.
    state = state_in(config={"config-dir": ""})
    with pytest.raises(testing.errors.UncaughtCharmError):
        ctx.run(ctx.on.config_changed(), state=state)


@patch("charm.update_charm_scripts")
@patch("charm.copy_ssh_keys")
@patch("charm.supervisord.supervisor_update")
@patch("charm.TestflingerAgentHostCharm.write_supervisor_service_files")
@patch("charm.supervisord.restart_agents")
@patch("charm.charm_utils.update_config_files")
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
@patch("charm.charm_utils.update_config_files")
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


@patch("testflinger_client.authenticate", return_value=True)
def test_secret_changed_active_on_successful_authentication(
    mock_authenticate, ctx, state_in, secret
):
    """Test active status when secret changes and authentication succeeds."""
    state = state_in(
        config={"credentials-secret": secret.id},
        secrets=[secret],
    )
    state_out = ctx.run(ctx.on.secret_changed(secret), state=state)
    assert state_out.unit_status == testing.ActiveStatus()


@patch("testflinger_client.authenticate", return_value=False)
def test_secret_changed_blocked_on_authentication_failure(
    mock_authenticate, ctx, state_in, secret
):
    """Test blocked status when secret changes but authentication fails."""
    state = state_in(
        config={"credentials-secret": secret.id},
        secrets=[secret],
    )
    state_out = ctx.run(ctx.on.secret_changed(secret), state=state)
    assert state_out.unit_status == testing.BlockedStatus(
        "Authentication with Testflinger server failed"
    )


@patch("charm.TestflingerAgentHostCharm._authenticate_with_server")
def test_authentication_triggered_on_update_status(
    mock_authenticate_with_server, ctx, state_in
):
    """Test that authentication is triggered on update_status event."""
    ctx.run(ctx.on.update_status(), state=state_in())
    mock_authenticate_with_server.assert_called_once()


@patch("charm.charm_utils.update_config_files")
@patch("charm.TestflingerAgentHostCharm.update_testflinger_repo")
@patch("charm.TestflingerAgentHostCharm.update_tf_cmd_scripts")
@patch("charm.charm_utils.setup_docker")
@patch("charm.TestflingerAgentHostCharm.install_dependencies")
def test_on_install_methods_called(
    mock_install_deps,
    mock_setup_docker,
    mock_update_tf_cmd_scripts,
    mock_update_testflinger_repo,
    mock_update_config_files,
    ctx,
    state_in,
):
    """Test that all expected methods are called during install."""
    ctx.run(ctx.on.install(), state=state_in())

    mock_install_deps.assert_called_once()
    mock_setup_docker.assert_called_once()
    mock_update_tf_cmd_scripts.assert_called_once()
    mock_update_testflinger_repo.assert_called_once()
    mock_update_config_files.assert_called_once()


def test_on_install_blocked_on_missing_config(ctx, state_in):
    """Test that install is blocked when required config is missing."""
    # Pydantic validation runs in __init__ via load_config(errors="blocked"),
    # which sets BlockedStatus and raises _Abort before the hook handler runs.
    state = state_in(config={"config-repo": ""})
    with pytest.raises(testing.errors.UncaughtCharmError):
        ctx.run(ctx.on.install(), state=state)


@patch("charm.supervisord.restart_agents")
@patch("charm.TestflingerAgentHostCharm.update_testflinger_repo")
def test_on_update_testflinger_action_with_branch(
    mock_update_testflinger_repo,
    mock_restart,
    ctx,
    state_in,
):
    """Test action call update testflinger code with the correct branch."""
    state_out = ctx.run(
        ctx.on.action("update-testflinger", params={"branch": "test-branch"}),
        state=state_in(),
    )
    mock_update_testflinger_repo.assert_called_once_with("test-branch")
    mock_restart.assert_called_once()
    assert state_out.unit_status == testing.ActiveStatus()


def test_update_configs_action_blocked_on_missing_config(ctx, state_in):
    """Test update-configs action is blocked when config is missing."""
    # Pydantic validation runs in __init__ via load_config(errors="blocked"),
    # which sets BlockedStatus and raises _Abort before the hook handler runs.
    state = state_in(config={"config-repo": ""})
    with pytest.raises(testing.errors.UncaughtCharmError):
        ctx.run(ctx.on.action("update-configs"), state=state)
