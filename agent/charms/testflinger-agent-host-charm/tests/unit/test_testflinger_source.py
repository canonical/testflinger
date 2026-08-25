# Copyright 2024 Canonical
# See LICENSE file for licensing details.
"""Unit tests for testflinger_source module."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import psutil
import pytest

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
    """Test venv creation and package installation."""
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


@patch("testflinger_source.datetime")
@patch("testflinger_source.shutil.rmtree")
@patch("testflinger_source.run_with_logged_errors", return_value=1)
def test_create_virtualenv_uv_venv_fails(mock_run, mock_rmtree, mock_datetime):
    """Test venv creation returns None when uv venv initialization fails."""
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    mock_datetime.now.return_value.strftime.return_value = timestamp
    expected_venv = Path(f"{VIRTUAL_ENV_PATH}-{timestamp}")

    result = testflinger_source.create_virtualenv(LOCAL_TESTFLINGER_PATH)

    assert result is None
    mock_rmtree.assert_called_once_with(expected_venv, ignore_errors=True)


@patch("testflinger_source.datetime")
@patch("testflinger_source.shutil.rmtree")
@patch("testflinger_source.run_with_logged_errors")
def test_create_virtualenv_package_install_fails(
    mock_run, mock_rmtree, mock_datetime
):
    """Test venv creation returns None and cleans up when a package install fails."""
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    mock_datetime.now.return_value.strftime.return_value = timestamp
    expected_venv = Path(f"{VIRTUAL_ENV_PATH}-{timestamp}")
    # uv venv succeeds, first pip install fails
    mock_run.side_effect = [0, 1]

    result = testflinger_source.create_virtualenv(LOCAL_TESTFLINGER_PATH)

    assert result is None
    mock_rmtree.assert_called_once_with(expected_venv, ignore_errors=True)


def test_update_virtualenv(tmp_path, monkeypatch):
    """Test that update_virtualenv atomically replaces the symlink."""
    new_venv = tmp_path / "tf-agent-venv-20260824_103045"
    new_venv.mkdir()
    live_venv = tmp_path / "tf-agent-venv"

    monkeypatch.setattr("testflinger_source.VIRTUAL_ENV_PATH", str(live_venv))
    testflinger_source.update_virtualenv(new_venv)

    assert live_venv.is_symlink()
    assert live_venv.resolve() == new_venv.resolve()


@patch("testflinger_source.os.replace", side_effect=OSError("replace failed"))
def test_update_virtualenv_raises_on_oserror(mock_replace, tmp_path, monkeypatch):
    """Test that update_virtualenv propagates OSError"""
    new_venv = tmp_path / "tf-agent-venv-20260824_103045"
    new_venv.mkdir()
    live_venv = tmp_path / "tf-agent-venv"

    monkeypatch.setattr("testflinger_source.VIRTUAL_ENV_PATH", str(live_venv))
    with pytest.raises(OSError):
        testflinger_source.update_virtualenv(new_venv)


@patch("testflinger_source.psutil.process_iter")
def test_is_venv_in_use_true_via_exe(mock_process_iter):
    """Test returns True when a process exe is inside the venv."""
    venv_path = Path("/srv/tf-agent-venv-20260824_103045")
    mock_proc = MagicMock()
    mock_proc.info = {
        "exe": str(venv_path / "bin" / "python3"),
        "open_files": [],
    }
    mock_process_iter.return_value = [mock_proc]

    assert testflinger_source.is_venv_in_use(venv_path) is True


@patch("testflinger_source.psutil.process_iter")
def test_is_venv_in_use_true_via_open_file(mock_process_iter):
    """Test returns True when a process has an open file inside the venv."""
    venv_path = Path("/srv/tf-agent-venv-20260824_103045")
    open_file = MagicMock()
    open_file.path = str(venv_path / "lib" / "python3.10" / "site.py")
    mock_proc = MagicMock()
    mock_proc.info = {
        "exe": "/usr/bin/python3",
        "open_files": [open_file],
    }
    mock_process_iter.return_value = [mock_proc]

    assert testflinger_source.is_venv_in_use(venv_path) is True


@patch("testflinger_source.psutil.process_iter")
def test_is_venv_in_use_false(mock_process_iter):
    """Test returns False when no process uses the venv."""
    venv_path = Path("/srv/tf-agent-venv-20260824_103045")
    mock_proc = MagicMock()
    mock_proc.info = {
        "exe": "/usr/bin/python3",
        "open_files": [],
    }
    mock_process_iter.return_value = [mock_proc]

    assert testflinger_source.is_venv_in_use(venv_path) is False


@patch("testflinger_source.psutil.process_iter")
def test_is_venv_in_use_handles_process_exceptions(mock_process_iter):
    """Test that psutil process exceptions are handled gracefully."""
    venv_path = Path("/srv/tf-agent-venv-20260824_103045")
    mock_proc = MagicMock()
    mock_proc.info = MagicMock()
    mock_proc.info.__getitem__ = MagicMock(
        side_effect=psutil.NoSuchProcess(pid=123)
    )
    mock_process_iter.return_value = [mock_proc]

    assert testflinger_source.is_venv_in_use(venv_path) is False


@patch("testflinger_source.shutil.rmtree")
@patch("testflinger_source.is_venv_in_use", return_value=False)
def test_cleanup_removes_unused_virtualenvs(mock_is_venv, mock_rmtree, tmp_path, monkeypatch):
    """Test that old venvs not in use are removed."""
    old_venv = tmp_path / "tf-agent-venv-20260824_100000"
    old_venv.mkdir()
    active_venv = tmp_path / "tf-agent-venv-20260824_110000"
    active_venv.mkdir()
    live_venv = tmp_path / "tf-agent-venv"
    live_venv.symlink_to(active_venv)

    monkeypatch.setattr("testflinger_source.VIRTUAL_ENV_PATH", str(live_venv))
    testflinger_source.cleanup_old_virtualenvs()

    mock_rmtree.assert_called_once_with(old_venv, ignore_errors=True)


@patch("testflinger_source.shutil.rmtree")
@patch("testflinger_source.is_venv_in_use", return_value=False)
def test_cleanup_skips_active_virtualenv(mock_is_venv, mock_rmtree, tmp_path, monkeypatch):
    """Test that the active venv (current symlink target) is not removed."""
    active_venv = tmp_path / "tf-agent-venv-20260824_110000"
    active_venv.mkdir()
    live_venv = tmp_path / "tf-agent-venv"
    live_venv.symlink_to(active_venv)

    monkeypatch.setattr("testflinger_source.VIRTUAL_ENV_PATH", str(live_venv))
    testflinger_source.cleanup_old_virtualenvs()

    mock_rmtree.assert_not_called()


@patch("testflinger_source.shutil.rmtree")
@patch("testflinger_source.is_venv_in_use", return_value=True)
def test_cleanup_skips_in_use_virtualenvs(mock_is_venv, mock_rmtree, tmp_path, monkeypatch):
    """Test that venvs still in use by running processes are not removed."""
    old_venv = tmp_path / "tf-agent-venv-20260824_100000"
    old_venv.mkdir()

    monkeypatch.setattr(
        "testflinger_source.VIRTUAL_ENV_PATH", str(tmp_path / "tf-agent-venv")
    )
    testflinger_source.cleanup_old_virtualenvs()

    mock_rmtree.assert_not_called()


@patch("testflinger_source.shutil.rmtree")
@patch("testflinger_source.is_venv_in_use", return_value=False)
def test_cleanup_no_active_symlink(mock_is_venv, mock_rmtree, tmp_path, monkeypatch):
    """Test cleanup is not made whenever there is no active symlink."""
    # On first deployment, there are no timestamped venvs and no symlink
    monkeypatch.setattr(
        "testflinger_source.VIRTUAL_ENV_PATH", str(tmp_path / "tf-agent-venv")
    )
    testflinger_source.cleanup_old_virtualenvs()

    mock_is_venv.assert_not_called()
    mock_rmtree.assert_not_called()
