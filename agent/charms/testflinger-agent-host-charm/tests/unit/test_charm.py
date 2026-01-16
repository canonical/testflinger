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
@patch("charm.TestflingerAgentHostCharm.restart_agents")
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
