# Copyright 2024 Canonical
# See LICENSE file for licensing details.
"""Unit tests for testflinger_source module."""

import os
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
    """Test venv creation cleanup is made when package installation fails."""
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
    new_venv = tmp_path / "testflinger-venv-20260824_103045"
    new_venv.mkdir()
    live_venv = tmp_path / "testflinger-venv"

    monkeypatch.setattr("testflinger_source.VIRTUAL_ENV_PATH", str(live_venv))
    testflinger_source.update_virtualenv(new_venv)

    assert live_venv.is_symlink()
    assert live_venv.resolve() == new_venv.resolve()


def test_update_virtualenv_migrates_legacy_dir(tmp_path, monkeypatch):
    """Test legacy real directory is renamed before creating the symlink."""
    new_venv = tmp_path / "testflinger-venv-20260824_103045"
    new_venv.mkdir()
    live_venv = tmp_path / "testflinger-venv"
    live_venv.mkdir()  # real dir — simulates pre-atomic installation

    monkeypatch.setattr("testflinger_source.VIRTUAL_ENV_PATH", str(live_venv))
    testflinger_source.update_virtualenv(new_venv)

    assert live_venv.is_symlink()
    assert live_venv.resolve() == new_venv.resolve()
    legacy_dirs = list(tmp_path.glob("testflinger-venv-*-legacy"))
    assert len(legacy_dirs) == 1


@patch("pathlib.Path.replace", side_effect=OSError("replace failed"))
def test_update_virtualenv_raises_on_oserror(
    mock_replace, tmp_path, monkeypatch
):
    """Test that update_virtualenv propagates OSError."""
    new_venv = tmp_path / "testflinger-venv-20260824_103045"
    new_venv.mkdir()
    live_venv = tmp_path / "testflinger-venv"

    monkeypatch.setattr("testflinger_source.VIRTUAL_ENV_PATH", str(live_venv))
    with pytest.raises(OSError):
        testflinger_source.update_virtualenv(new_venv)


@patch("testflinger_source.psutil.process_iter")
@patch("testflinger_source.shutil.rmtree")
def test_cleanup_removes_unused_virtualenvs(
    mock_rmtree, mock_process_iter, tmp_path, monkeypatch
):
    """Test that old venvs are removed when all agents postdate the symlink."""
    old_venv = tmp_path / "testflinger-venv-20260824_100000"
    old_venv.mkdir()
    active_venv = tmp_path / "testflinger-venv-20260824_110000"
    active_venv.mkdir()
    live_venv = tmp_path / "testflinger-venv"
    live_venv.symlink_to(active_venv)

    symlink_mtime = 1000.0
    os.utime(
        str(live_venv),
        times=(symlink_mtime, symlink_mtime),
        follow_symlinks=False,
    )

    mock_proc = MagicMock()
    mock_proc.info = {
        "cmdline": ["testflinger-agent", "--config", "test.conf"],
        "create_time": 2000.0,
    }
    mock_process_iter.return_value = [mock_proc]

    monkeypatch.setattr("testflinger_source.VIRTUAL_ENV_PATH", str(live_venv))
    testflinger_source.cleanup_old_virtualenvs()

    mock_rmtree.assert_called_once_with(old_venv, ignore_errors=True)


@patch("testflinger_source.psutil.process_iter")
@patch("testflinger_source.shutil.rmtree")
def test_cleanup_skips_active_virtualenv(
    mock_rmtree, mock_process_iter, tmp_path, monkeypatch
):
    """Test that the active venv (current symlink target) is not removed."""
    active_venv = tmp_path / "testflinger-venv-20260824_110000"
    active_venv.mkdir()
    live_venv = tmp_path / "testflinger-venv"
    live_venv.symlink_to(active_venv)

    mock_process_iter.return_value = []

    monkeypatch.setattr("testflinger_source.VIRTUAL_ENV_PATH", str(live_venv))
    testflinger_source.cleanup_old_virtualenvs()

    mock_rmtree.assert_not_called()


@patch("testflinger_source.psutil.process_iter")
@patch("testflinger_source.shutil.rmtree")
def test_cleanup_skips_in_use_virtualenvs(
    mock_rmtree, mock_process_iter, tmp_path, monkeypatch
):
    """Test that old venvs are kept when an agent predates the symlink."""
    old_venv = tmp_path / "testflinger-venv-20260824_100000"
    old_venv.mkdir()
    active_venv = tmp_path / "testflinger-venv-20260824_110000"
    active_venv.mkdir()
    live_venv = tmp_path / "testflinger-venv"
    live_venv.symlink_to(active_venv)

    symlink_mtime = 1000.0
    os.utime(
        str(live_venv),
        times=(symlink_mtime, symlink_mtime),
        follow_symlinks=False,
    )

    mock_proc = MagicMock()
    mock_proc.info = {
        "cmdline": ["testflinger-agent", "--config", "test.conf"],
        "create_time": 500.0,
    }
    mock_process_iter.return_value = [mock_proc]

    monkeypatch.setattr("testflinger_source.VIRTUAL_ENV_PATH", str(live_venv))
    testflinger_source.cleanup_old_virtualenvs()

    mock_rmtree.assert_not_called()


@patch("testflinger_source.psutil.process_iter")
@patch("testflinger_source.shutil.rmtree")
def test_cleanup_ignores_non_agent_processes(
    mock_rmtree, mock_process_iter, tmp_path, monkeypatch
):
    """Test that non-agent processes do not prevent venv cleanup."""
    old_venv = tmp_path / "testflinger-venv-20260824_100000"
    old_venv.mkdir()
    active_venv = tmp_path / "testflinger-venv-20260824_110000"
    active_venv.mkdir()
    live_venv = tmp_path / "testflinger-venv"
    live_venv.symlink_to(active_venv)

    symlink_mtime = 1000.0
    os.utime(
        str(live_venv),
        times=(symlink_mtime, symlink_mtime),
        follow_symlinks=False,
    )

    # Non-agent process with old create_time should not block removal
    mock_proc = MagicMock()
    mock_proc.info = {
        "cmdline": ["/usr/bin/python3", "some_other_script.py"],
        "create_time": 100.0,
    }
    mock_process_iter.return_value = [mock_proc]

    monkeypatch.setattr("testflinger_source.VIRTUAL_ENV_PATH", str(live_venv))
    testflinger_source.cleanup_old_virtualenvs()

    mock_rmtree.assert_called_once_with(old_venv, ignore_errors=True)


@patch("testflinger_source.psutil.process_iter")
@patch("testflinger_source.shutil.rmtree")
def test_cleanup_no_active_symlink(
    mock_rmtree, mock_process_iter, tmp_path, monkeypatch
):
    """Test cleanup does nothing when there is no active symlink."""
    monkeypatch.setattr(
        "testflinger_source.VIRTUAL_ENV_PATH",
        str(tmp_path / "testflinger-venv"),
    )
    testflinger_source.cleanup_old_virtualenvs()

    mock_process_iter.assert_not_called()
    mock_rmtree.assert_not_called()


@patch("testflinger_source.psutil.process_iter")
@patch("testflinger_source.shutil.rmtree")
def test_cleanup_handles_process_exceptions(
    mock_rmtree, mock_process_iter, tmp_path, monkeypatch
):
    """Test that psutil exceptions during process collection are ignored."""
    old_venv = tmp_path / "testflinger-venv-20260824_100000"
    old_venv.mkdir()
    active_venv = tmp_path / "testflinger-venv-20260824_110000"
    active_venv.mkdir()
    live_venv = tmp_path / "testflinger-venv"
    live_venv.symlink_to(active_venv)

    symlink_mtime = 1000.0
    os.utime(
        str(live_venv),
        times=(symlink_mtime, symlink_mtime),
        follow_symlinks=False,
    )

    # Simulate a process that raises NoSuchProcess when its info is accessed
    bad_proc = MagicMock()
    bad_proc.info = MagicMock()
    bad_proc.info.get = MagicMock(side_effect=psutil.NoSuchProcess(pid=999))
    mock_process_iter.return_value = [bad_proc]

    monkeypatch.setattr("testflinger_source.VIRTUAL_ENV_PATH", str(live_venv))
    testflinger_source.cleanup_old_virtualenvs()

    # Exception swallowed, old venv removed (no agents blocking it)
    mock_rmtree.assert_called_once_with(old_venv, ignore_errors=True)


@patch("testflinger_source.psutil.process_iter")
@patch("testflinger_source.shutil.rmtree")
def test_cleanup_per_venv_independent_removal(
    mock_rmtree, mock_process_iter, tmp_path, monkeypatch
):
    """Test that each old venv is evaluated independently.

    With multiple old venvs, an in-use venv should not prevent cleanup of
    older venvs that have already been superseded before the oldest running
    agent was started.
    """
    # Three old venvs, sorted chronologically by name
    venv_old = tmp_path / "testflinger-venv-20260821_000000"
    venv_mid = tmp_path / "testflinger-venv-20260822_000000"
    venv_prev = tmp_path / "testflinger-venv-20260823_000000"
    active_venv = tmp_path / "testflinger-venv-20260824_000000"
    for d in (venv_old, venv_mid, venv_prev, active_venv):
        d.mkdir()

    live_venv = tmp_path / "testflinger-venv"
    live_venv.symlink_to(active_venv)

    # venv_mid.mtime = 500 (venv_old's cutoff)
    # venv_prev.mtime = 1000 (venv_mid's cutoff)
    # symlink.mtime = 2000 (venv_prev's cutoff)
    os.utime(str(venv_mid), times=(500.0, 500.0))
    os.utime(str(venv_prev), times=(1000.0, 1000.0))
    os.utime(str(live_venv), times=(2000.0, 2000.0), follow_symlinks=False)

    # An agent started at 700 — after venv_old was superseded (500) but before
    # venv_mid was superseded (1000), so venv_mid and venv_prev must be kept.
    mock_proc = MagicMock()
    mock_proc.info = {
        "cmdline": ["testflinger-agent", "--config", "test.conf"],
        "create_time": 700.0,
    }
    mock_process_iter.return_value = [mock_proc]

    monkeypatch.setattr("testflinger_source.VIRTUAL_ENV_PATH", str(live_venv))
    testflinger_source.cleanup_old_virtualenvs()

    # Only venv_old should be removed; venv_mid and venv_prev still in use
    mock_rmtree.assert_called_once_with(venv_old, ignore_errors=True)
