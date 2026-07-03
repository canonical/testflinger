# Copyright 2024 Canonical
# See LICENSE file for licensing details.
"""Unit tests for testflinger_source module."""

from pathlib import Path
from unittest.mock import call, patch

import testflinger_source
from defaults import (
    DEFAULT_BRANCH,
    DEFAULT_TESTFLINGER_REPO,
    LOCAL_TESTFLINGER_PATH,
    UV_BIN_PATH,
    VIRTUAL_ENV_PATH,
)

_FAKE_TMP_DIR = "/srv/tmp_venv_test"


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


@patch("testflinger_source.shutil.rmtree")
@patch("pathlib.Path.rename")
@patch("pathlib.Path.exists", return_value=False)
@patch("testflinger_source.tempfile.mkdtemp", return_value=_FAKE_TMP_DIR)
@patch("testflinger_source.run_with_logged_errors")
def test_create_new_virtualenv(
    mock_run,
    mock_mkdtemp,
    mock_exists,
    mock_rename,
    mock_rmtree,
):
    """Test that create_virtualenv builds a temp venv and puts it into place."""
    testflinger_source.create_virtualenv(LOCAL_TESTFLINGER_PATH)

    # Packages must be installed into the temporary virtualenv
    mock_run.assert_any_call([UV_BIN_PATH, "venv", _FAKE_TMP_DIR])
    mock_run.assert_called_with(
        [
            UV_BIN_PATH,
            "pip",
            "install",
            "--python",
            f"{_FAKE_TMP_DIR}/bin/python3",
            "-U",
            f"{LOCAL_TESTFLINGER_PATH}/device-connectors",
        ]
    )
    # The temp venv must be renamed into the live location
    mock_rename.assert_called_once_with(Path(VIRTUAL_ENV_PATH))


@patch("testflinger_source.shutil.rmtree")
@patch("pathlib.Path.rename")
@patch("pathlib.Path.exists", return_value=True)
@patch("testflinger_source.tempfile.mkdtemp", return_value=_FAKE_TMP_DIR)
@patch("testflinger_source.run_with_logged_errors")
def test_create_virtualenv_replaces_existing(
    mock_run,
    mock_mkdtemp,
    mock_exists,
    mock_rename,
    mock_rmtree,
):
    """Test create_virtualenv moves the old venv aside before swapping in the new one."""
    testflinger_source.create_virtualenv(LOCAL_TESTFLINGER_PATH)

    old_venv_backup = f"{VIRTUAL_ENV_PATH}.old"
    # Must first rename the live venv to a backup, then rename temp into place
    assert mock_rename.call_args_list == [
        call(old_venv_backup),
        call(Path(VIRTUAL_ENV_PATH)),
    ]
    # Backup must be cleaned up after a successful swap
    mock_rmtree.assert_any_call(old_venv_backup, ignore_errors=True)


@patch("testflinger_source.shutil.rmtree")
@patch("pathlib.Path.rename")
@patch("pathlib.Path.exists", return_value=True)
@patch("testflinger_source.tempfile.mkdtemp", return_value=_FAKE_TMP_DIR)
@patch("testflinger_source.run_with_logged_errors")
def test_create_virtualenv_restores_backup_on_failure(
    mock_run,
    mock_mkdtemp,
    mock_exists,
    mock_rename,
    mock_rmtree,
):
    """Test that the old venv is restored when the swap rename fails."""
    old_venv_backup = f"{VIRTUAL_ENV_PATH}.old"
    # 1: backup rename succeeded
    # 2: swap rename failed
    # 3: restore rename succeeded
    mock_rename.side_effect = [None, OSError("rename failed"), None]

    testflinger_source.create_virtualenv(LOCAL_TESTFLINGER_PATH)

    assert mock_rename.call_args_list == [
        call(old_venv_backup),
        call(Path(VIRTUAL_ENV_PATH)),
        call(Path(VIRTUAL_ENV_PATH)),
    ]
    # No backup cleanup needed
    # The restore renamed it back to the production path
    mock_rmtree.assert_called_once_with(_FAKE_TMP_DIR, ignore_errors=True)


@patch("testflinger_source.shutil.rmtree")
@patch("pathlib.Path.rename")
@patch("pathlib.Path.exists", return_value=True)
@patch("testflinger_source.tempfile.mkdtemp", return_value=_FAKE_TMP_DIR)
@patch("testflinger_source.run_with_logged_errors")
def test_create_virtualenv_on_rename_failures(
    mock_run,
    mock_mkdtemp,
    mock_exists,
    mock_rename,
    mock_rmtree,
    caplog,
):
    """Test that the backup path is logged when both the swap and restore fail."""
    old_venv_backup = f"{VIRTUAL_ENV_PATH}.old"
    # 1: backup rename succeeded
    # 2: swap rename failed
    # 3: restore rename failed
    mock_rename.side_effect = [
        None,
        OSError("rename failed"),
        OSError("restore failed"),
    ]

    testflinger_source.create_virtualenv(LOCAL_TESTFLINGER_PATH)

    # The path to the old venv backup must be logged when both renames fail
    assert old_venv_backup in caplog.text
