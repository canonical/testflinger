# Copyright 2024 Canonical
# See LICENSE file for licensing details.
"""Unit tests for testflinger_source module."""

import fcntl
import os
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

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


@patch("testflinger_source.write_file")
@patch("testflinger_source.datetime")
@patch("testflinger_source.run_with_logged_errors", return_value=0)
def test_create_new_virtualenv(mock_run, mock_datetime, mock_write_file):
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
    # Must pre-create the lock file so non-root consumers can flock it
    mock_write_file.assert_called_once_with(
        location=expected_venv / testflinger_source.VENV_LOCK_FILENAME,
        contents="",
    )
    # Must return the new venv path on success
    assert result == expected_venv


@patch("testflinger_source.datetime")
@patch("testflinger_source.shutil.rmtree")
@patch("testflinger_source.write_file", side_effect=OSError)
@patch("testflinger_source.run_with_logged_errors", return_value=0)
def test_create_virtualenv_lock_file_creation_fails(
    mock_run, mock_write_file, mock_rmtree, mock_datetime
):
    """Test venv creation returns None when lock file creation fails."""
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    mock_datetime.now.return_value.strftime.return_value = timestamp
    expected_venv = Path(f"{VIRTUAL_ENV_PATH}-{timestamp}")

    result = testflinger_source.create_virtualenv(LOCAL_TESTFLINGER_PATH)

    mock_rmtree.assert_called_once_with(expected_venv, ignore_errors=True)
    assert result is None


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


def test_update_virtualenv_bumps_deactivated_venv_mtime(tmp_path, monkeypatch):
    """Test that swapping away from a venv refreshes its mtime.

    This lets cleanup_old_virtualenvs()'s grace period protect the venv
    for a while after deactivation, even if it was created long ago —
    covering processes (e.g. the main agent) that have not yet noticed
    the swap and restarted against the new symlink target.
    """
    old_venv = tmp_path / "testflinger-venv-20260824_090000"
    old_venv.mkdir()
    old_timestamp = datetime.now(tz=timezone.utc).timestamp() - 10_000
    os.utime(old_venv, times=(old_timestamp, old_timestamp))

    new_venv = tmp_path / "testflinger-venv-20260824_103045"
    new_venv.mkdir()
    live_venv = tmp_path / "testflinger-venv"
    live_venv.symlink_to(old_venv)

    monkeypatch.setattr("testflinger_source.VIRTUAL_ENV_PATH", str(live_venv))
    testflinger_source.update_virtualenv(new_venv)

    assert live_venv.resolve() == new_venv.resolve()
    now = datetime.now(tz=timezone.utc).timestamp()
    assert now - old_venv.stat().st_mtime < 5


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


def _age(path: Path, seconds_old: float) -> None:
    """Set a path's mtime to be `seconds_old` seconds in the past."""
    timestamp = datetime.now(tz=timezone.utc).timestamp() - seconds_old
    os.utime(str(path), times=(timestamp, timestamp), follow_symlinks=False)


def _lock_venv(venv: Path) -> int:
    """Open and hold a shared flock on a venv's lock file.

    :return: The open fd holding the lock. Caller is responsible for
        closing it (which releases the lock) once the test is done.
    """
    lock_path = venv / testflinger_source.VENV_LOCK_FILENAME
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(fd, fcntl.LOCK_SH)
    return fd


@patch("testflinger_source.shutil.rmtree")
def test_cleanup_removes_unused_virtualenvs(
    mock_rmtree, tmp_path, monkeypatch
):
    """Test that an old, unlocked venv (past the grace period) is removed."""
    old_venv = tmp_path / "testflinger-venv-20260824_100000"
    old_venv.mkdir()
    _age(old_venv, testflinger_source.MIN_VENV_AGE_SECONDS + 60)
    active_venv = tmp_path / "testflinger-venv-20260824_110000"
    active_venv.mkdir()
    live_venv = tmp_path / "testflinger-venv"
    live_venv.symlink_to(active_venv)

    monkeypatch.setattr("testflinger_source.VIRTUAL_ENV_PATH", str(live_venv))
    testflinger_source.cleanup_old_virtualenvs()

    mock_rmtree.assert_called_once_with(old_venv, ignore_errors=True)


@patch("testflinger_source.shutil.rmtree")
def test_cleanup_skips_active_virtualenv(mock_rmtree, tmp_path, monkeypatch):
    """Test that the active venv (current symlink target) is not removed."""
    active_venv = tmp_path / "testflinger-venv-20260824_110000"
    active_venv.mkdir()
    _age(active_venv, testflinger_source.MIN_VENV_AGE_SECONDS + 60)
    live_venv = tmp_path / "testflinger-venv"
    live_venv.symlink_to(active_venv)

    monkeypatch.setattr("testflinger_source.VIRTUAL_ENV_PATH", str(live_venv))
    testflinger_source.cleanup_old_virtualenvs()

    mock_rmtree.assert_not_called()


@patch("testflinger_source.shutil.rmtree")
def test_cleanup_skips_in_use_virtualenvs(mock_rmtree, tmp_path, monkeypatch):
    """Test that an old venv still holding a lock is kept."""
    old_venv = tmp_path / "testflinger-venv-20260824_100000"
    old_venv.mkdir()
    _age(old_venv, testflinger_source.MIN_VENV_AGE_SECONDS + 60)
    active_venv = tmp_path / "testflinger-venv-20260824_110000"
    active_venv.mkdir()
    live_venv = tmp_path / "testflinger-venv"
    live_venv.symlink_to(active_venv)

    fd = _lock_venv(old_venv)
    try:
        monkeypatch.setattr(
            "testflinger_source.VIRTUAL_ENV_PATH", str(live_venv)
        )
        testflinger_source.cleanup_old_virtualenvs()
    finally:
        os.close(fd)

    mock_rmtree.assert_not_called()


@patch("testflinger_source.shutil.rmtree")
def test_cleanup_respects_grace_period(mock_rmtree, tmp_path, monkeypatch):
    """Test that a recently created, unlocked venv is not removed yet."""
    recent_venv = tmp_path / "testflinger-venv-20260824_100000"
    recent_venv.mkdir()
    active_venv = tmp_path / "testflinger-venv-20260824_110000"
    active_venv.mkdir()
    _age(active_venv, testflinger_source.MIN_VENV_AGE_SECONDS + 60)
    live_venv = tmp_path / "testflinger-venv"
    live_venv.symlink_to(active_venv)

    monkeypatch.setattr("testflinger_source.VIRTUAL_ENV_PATH", str(live_venv))
    testflinger_source.cleanup_old_virtualenvs()

    mock_rmtree.assert_not_called()


@patch("testflinger_source.shutil.rmtree")
def test_cleanup_no_active_symlink(mock_rmtree, tmp_path, monkeypatch):
    """Test cleanup does nothing when there is no active symlink."""
    monkeypatch.setattr(
        "testflinger_source.VIRTUAL_ENV_PATH",
        str(tmp_path / "testflinger-venv"),
    )
    testflinger_source.cleanup_old_virtualenvs()

    mock_rmtree.assert_not_called()


@patch("testflinger_source.shutil.rmtree")
def test_cleanup_per_venv_independent_removal(
    mock_rmtree, tmp_path, monkeypatch
):
    """Test that each old venv is evaluated independently.

    Reproduces the reported gap: an agent still running against venv1 and
    an agent restarted onto venv3 must not prevent removal of venv2, which
    nobody holds a lock on.
    """
    venv1 = tmp_path / "testflinger-venv-20260821_000000"
    venv2 = tmp_path / "testflinger-venv-20260822_000000"
    venv3 = tmp_path / "testflinger-venv-20260823_000000"
    for d in (venv1, venv2, venv3):
        d.mkdir()
        _age(d, testflinger_source.MIN_VENV_AGE_SECONDS + 60)

    live_venv = tmp_path / "testflinger-venv"
    live_venv.symlink_to(venv3)

    # agent1 still running against venv1; agent2 restarted onto venv3
    # (the active symlink target, so it's excluded from consideration
    # regardless of locking). venv2 has no holder.
    fd1 = _lock_venv(venv1)
    fd3 = _lock_venv(venv3)
    try:
        monkeypatch.setattr(
            "testflinger_source.VIRTUAL_ENV_PATH", str(live_venv)
        )
        testflinger_source.cleanup_old_virtualenvs()
    finally:
        os.close(fd1)
        os.close(fd3)

    mock_rmtree.assert_called_once_with(venv2, ignore_errors=True)
