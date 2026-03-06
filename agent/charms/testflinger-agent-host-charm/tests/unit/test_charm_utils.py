# Copyright 2026 Canonical
# See LICENSE file for licensing details.

from unittest.mock import patch

import charm_utils
import pytest


@patch("charm_utils.apt.add_package")
@patch("charm_utils.apt.update")
def test_install_agent_packages_calls_apt(mock_update, mock_add_package):
    """Test that install_agent_packages calls update add_package."""
    charm_utils.install_agent_packages()

    mock_update.assert_called_once()
    mock_add_package.assert_called_once_with(charm_utils.AGENT_PACKAGES)


@patch("charm_utils.passwd.add_user_to_group")
@patch("charm_utils.passwd.add_group")
def test_setup_docker_calls_adds_group_and_adds_user_to_group(
    mock_add_group, mock_add_user
):
    """Test add_group and add_user_to_group are called with correct params."""
    charm_utils.setup_docker()

    mock_add_group.assert_called_once_with(charm_utils.DOCKER_GROUP)
    mock_add_user.assert_called_once_with(
        charm_utils.CHARM_USER, charm_utils.DOCKER_GROUP
    )


@patch("charm_utils.shutil.move")
@patch("charm_utils.shutil.rmtree")
@patch("charm_utils.Repo.clone_from")
@patch("charm_utils.Path.exists", return_value=False)
def test_update_config_files_calls_clone_and_move(
    mock_exists, mock_clone, mock_rmtree, mock_move, config
):
    """Test clone_from and move are called during update_config_files."""
    charm_utils.update_config_files(config)

    mock_clone.assert_called_once_with(
        url=config.config_repo,
        branch=config.config_branch,
        to_path=charm_utils.Path("/srv/tmp-agent-configs"),
        depth=1,
    )
    mock_move.assert_called_once()


@patch("charm_utils.shutil.move")
@patch("charm_utils.shutil.rmtree")
@patch("charm_utils.Repo.clone_from")
@patch("charm_utils.Path.exists", return_value=True)
def test_update_config_files_calls_removal_of_existing_paths(
    mock_exists, mock_clone, mock_rmtree, mock_move, config
):
    """Test correct paths are called for removal when they exist."""
    charm_utils.update_config_files(config)

    assert mock_rmtree.call_count == 2
    mock_rmtree.assert_any_call(charm_utils.Path("/srv/tmp-agent-configs"))
    mock_rmtree.assert_any_call(
        charm_utils.Path(charm_utils.AGENT_CONFIGS_PATH)
    )


@patch(
    "charm_utils.Repo.clone_from",
    side_effect=charm_utils.GitCommandError("clone", "failed"),
)
@patch("charm_utils.Path.exists", return_value=False)
def test_update_config_files_raises_runtime_error_on_git_failure(
    mock_exists, mock_clone, config
):
    """Test that a GitCommandError is re-raised as RuntimeError."""
    with pytest.raises(RuntimeError, match="Failed to update or config files"):
        charm_utils.update_config_files(config)
