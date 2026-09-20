# Copyright 2024 Canonical
# See LICENSE file for licensing details.
"""Module for managing Testflinger agent source code."""

import fcntl
import logging
import os
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from git import Repo

from common import run_with_logged_errors, write_file
from defaults import (
    DEFAULT_BRANCH,
    DEFAULT_TESTFLINGER_REPO,
    UV_BIN_PATH,
    VIRTUAL_ENV_PATH,
)

# Only keep these directories from the repo in the sparse checkout
TESTFLINGER_PACKAGES = ("agent", "common", "device-connectors")

# Name of the advisory lock file held (via flock) inside a virtualenv
# directory by any process that depends on that specific venv.
VENV_LOCK_FILENAME = ".venv.lock"

# Minimum age a venv must have before it is eligible for
# removal. This is measured from the venv's mtime, which reflects either
# its creation time or the moment it was deactivated.
MIN_VENV_AGE_SECONDS = 60

logger = logging.getLogger(__name__)


def clone_repo(
    local_path: str,
    testflinger_repo: str = DEFAULT_TESTFLINGER_REPO,
    branch: str = DEFAULT_BRANCH,
):
    """Clone the Testflinger repository with a sparse checkout.

    :param local_path: The local path where the repo should be cloned.
    :param testflinger_repo: The URL of the Testflinger repository.
    :param branch: The branch to clone from the repository.
    """
    # First, remove the old repo
    shutil.rmtree(local_path, ignore_errors=True)

    # Clone the repo
    logger.debug("Cloning Testflinger repository: %s", testflinger_repo)
    repo = Repo.clone_from(
        url=testflinger_repo,
        branch=branch,
        to_path=local_path,
        no_checkout=True,
        depth=1,
    )

    # do a sparse checkout of only the parts of the repo we need
    repo.git.checkout(f"origin/{branch}", "--", *TESTFLINGER_PACKAGES)


def create_virtualenv(local_path: str) -> Path | None:
    """Build a virtualenv and install the Testflinger packages into it.

    A unique timestamp is added to the virtualenv name to avoid conflicts
    with previous builds.

    :param local_path: The local path where the Testflinger repo is located.
    :return: The path to the new virtualenv if successful, None otherwise.
    """
    venv_path = Path(VIRTUAL_ENV_PATH)
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    new_venv = venv_path.parent / f"{venv_path.name}-{timestamp}"

    # Initialize the new virtualenv
    logger.debug("Creating new virtualenv: %s", new_venv)
    if run_with_logged_errors([UV_BIN_PATH, "venv", str(new_venv)]) != 0:
        logger.error("Failed to initialize virtualenv: %s", new_venv)
        shutil.rmtree(new_venv, ignore_errors=True)
        return None

    # Install the testflinger packages into the new virtualenv
    for tf_package in TESTFLINGER_PACKAGES:
        logger.debug("Installing Python package: %s", tf_package)
        return_code = run_with_logged_errors(
            [
                UV_BIN_PATH,
                "pip",
                "install",
                "--python",
                f"{new_venv}/bin/python3",
                "-U",
                f"{local_path}/{tf_package}",
            ]
        )
        # terminate the installation if any package fails to install
        if return_code != 0:
            logger.error("Failed to install package: %s", tf_package)
            shutil.rmtree(new_venv, ignore_errors=True)
            return None

    # Pre-create the venv's advisory lock file
    # During this process, the ownership changes to the ubuntu user
    # so that the agent process can acquire a shared lock on
    try:
        write_file(location=new_venv / VENV_LOCK_FILENAME, contents="")
    except OSError:
        logger.error(
            "Failed to prepare lock file for virtualenv: %s", new_venv
        )
        shutil.rmtree(new_venv, ignore_errors=True)
        return None

    logger.info("Successfully created virtualenv: %s", new_venv)
    return new_venv


def update_virtualenv(new_venv: Path):
    """Atomically replace the working virtualenv with the new one.

    For atomicity, a temporary symlink is created and then renamed
    to the target path where the virtualenv resides.

    On first deployment, VIRTUAL_ENV_PATH may be a real directory left
    by the previous non-atomic install. It is renamed to a timestamped
    path so the symlink can be properly created

    :param new_venv: The path to the new virtualenv.
    """
    venv_path = Path(VIRTUAL_ENV_PATH)

    # Capture the currently active venv (if any) before swapping, so it
    # can be marked as just-deactivated once the swap completes below.
    previously_active = venv_path.resolve() if venv_path.is_symlink() else None

    # Migrate a legacy real directory to a timestamped backup
    if venv_path.exists() and not venv_path.is_symlink():
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        legacy = venv_path.parent / f"{venv_path.name}-{timestamp}-legacy"
        logger.info(
            "Migrating legacy virtualenv directory %s to %s",
            venv_path,
            legacy,
        )
        venv_path.rename(legacy)

    # Attempt to create a temporary symlink and replace the existing symlink.
    # Failures are bubbled up to the caller to handle.
    tmp = tempfile.NamedTemporaryFile(
        dir=new_venv.parent, prefix="tmp_link_", delete=False
    )
    tmp_symlink = Path(tmp.name)
    tmp.close()
    # Remove the placeholder file so we can create a symlink at the same path
    tmp_symlink.unlink(missing_ok=True)
    try:
        tmp_symlink.symlink_to(new_venv)
        tmp_symlink.replace(venv_path)
    finally:
        # If the replace fails, avoid leaving tmp_link_* behind
        tmp_symlink.unlink(missing_ok=True)

    # Bump the mtime of the venv that was just deactivated so that
    # cleanup grace period is measured from the moment it stopped being
    # active, not from its creation time.
    if previously_active is not None and previously_active != new_venv:
        try:
            os.utime(previously_active)
        except OSError:
            logger.warning(
                "Could not update mtime for deactivated virtualenv: %s",
                previously_active,
            )


def _is_venv_in_use(venv: Path) -> bool:
    """Check whether any process currently depends on this venv.

    A venv is considered in use if a shared advisory lock (flock) is held
    on its lock file by another process.

    :param venv: The path to the virtualenv directory to check.
    :return: True if the venv is still in use, False otherwise.
    """
    lock_path = venv / VENV_LOCK_FILENAME

    # Conservatively assume the venv is in use if we can't open its lock file
    try:
        file_descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    except OSError:
        logger.warning("Could not open lock file for %s", venv)
        return True

    # Attempt to acquire a non-blocking exclusive lock on the venv's lock file
    try:
        fcntl.flock(file_descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        # If we can't exclusively lock the file, in use by another process
        return True
    else:
        # If we successfully acquired the lock, release it immediately
        fcntl.flock(file_descriptor, fcntl.LOCK_UN)
        return False
    finally:
        os.close(file_descriptor)


def cleanup_old_virtualenvs():
    """Remove old virtualenvs that are no longer in use.

    A venv is considered safe to remove once no process holds an advisory
    lock (flock) on it.
    """
    venv_path = Path(VIRTUAL_ENV_PATH)
    if not venv_path.is_symlink():
        return

    active_symlink = venv_path.resolve()

    # Find all old venvs that match the naming pattern and are not the
    # active one.
    old_venvs = (
        venv
        for venv in venv_path.parent.glob(f"{venv_path.name}-*")
        if venv.is_dir() and venv.resolve() != active_symlink
    )

    now = time.time()
    for old_venv in old_venvs:
        # Skip venvs that were only just created, to avoid a race with a
        # process that has been spawned against this venv but has not yet
        # had a chance to acquire its lock.
        if now - old_venv.stat().st_mtime < MIN_VENV_AGE_SECONDS:
            logger.debug("Skipping recently created virtualenv: %s", old_venv)
            continue

        if _is_venv_in_use(old_venv):
            logger.debug("Skipping in-use virtualenv: %s", old_venv)
            continue

        logger.info("Removing old virtualenv: %s", old_venv)
        shutil.rmtree(old_venv, ignore_errors=True)
