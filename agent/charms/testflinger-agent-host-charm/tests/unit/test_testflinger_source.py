# Copyright 2024 Canonical
# See LICENSE file for licensing details.
"""Unit tests for testflinger_source module."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import testflinger_source
from defaults import (
    DEFAULT_BRANCH,
    DEFAULT_TESTFLINGER_REPO,
    LOCAL_TESTFLINGER_PATH,
    UV_BIN_PATH,
    VIRTUAL_ENV_PATH,
)


@patch("git.Repo.clone_from")
def test_clone_repo(mock_clone_from):
    """Test that clone_repo clones the repo and does a sparse checkout."""
    testflinger_source.clone_repo(LOCAL_TESTFLINGER_PATH)

    mock_clone_from.assert_called_once_with(
        url=DEFAULT_TESTFLINGER_REPO,
        branch=DEFAULT_BRANCH,
        to_path=LOCAL_TESTFLINGER_PATH,
        no_checkout=True,
        depth=1,
    )
    mock_clone_from.return_value.git.checkout.assert_called_once_with(
        f"origin/{DEFAULT_BRANCH}",
        "--",
        *testflinger_source.TESTFLINGER_PACKAGES,
    )


@patch("testflinger_source.datetime")
@patch("testflinger_source.run_with_logged_errors", return_value=0)
def test_create_new_virtualenv(mock_run, mock_datetime):
    """Test building a new virtualenv and installing Testflinger packages."""
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    mock_datetime.now.return_value.strftime.return_value = timestamp
    expected_venv = Path(f"{VIRTUAL_ENV_PATH}-{timestamp}")

    result = testflinger_source.create_virtualenv(LOCAL_TESTFLINGER_PATH)

    # First call must initialize the venv at the timestamped path
    mock_run.assert_any_call([UV_BIN_PATH, "venv", str(expected_venv)])
    # Last call must be the final package installation
    mock_run.assert_called_with(
        [
            UV_BIN_PATH,
            "pip",
            "install",
            "--python",
            f"{expected_venv}/bin/python3",
            "-U",
            f"{LOCAL_TESTFLINGER_PATH}/device-connectors",
        ]
    )
    # Must return the new venv path on success
    assert result == expected_venv
