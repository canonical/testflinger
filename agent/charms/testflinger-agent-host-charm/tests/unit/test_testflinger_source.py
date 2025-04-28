# Copyright 2024 Canonical
# See LICENSE file for licensing details.

from unittest.mock import patch

import testflinger_source
from defaults import (
    DEFAULT_BRANCH,
    DEFAULT_TESTFLINGER_REPO,
    LOCAL_TESTFLINGER_PATH,
    VIRTUAL_ENV_PATH,
)


@patch("git.Repo.clone_from")
@patch("testflinger_source.run_with_logged_errors")
def test_clone_repo(mock_run_with_logged_errors, mock_clone_from):
    """Test the clone_repo method."""
    testflinger_source.clone_repo(LOCAL_TESTFLINGER_PATH)
    mock_clone_from.assert_called_once_with(
        url=DEFAULT_TESTFLINGER_REPO,
        branch=DEFAULT_BRANCH,
        to_path=LOCAL_TESTFLINGER_PATH,
        no_checkout=True,
        depth=1,
    )
    mock_run_with_logged_errors.assert_called_with(
        [
            f"{VIRTUAL_ENV_PATH}/bin/pip3",
            "install",
            "-U",
            f"{LOCAL_TESTFLINGER_PATH}/device-connectors",
        ]
    )


@patch("testflinger_source.run_with_logged_errors")
def test_create_virtualenv(mock_run_with_logged_errors):
    """Test the create_virtualenv method."""
    testflinger_source.create_virtualenv()
    mock_run_with_logged_errors.assert_any_call(
        ["python3", "-m", "virtualenv", VIRTUAL_ENV_PATH]
    )
    mock_run_with_logged_errors.assert_any_call(
        [f"{VIRTUAL_ENV_PATH}/bin/pip3", "install", "-U", "pip"]
    )
