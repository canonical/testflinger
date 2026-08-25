# Copyright 2024 Canonical
# See LICENSE file for licensing details.
"""Module for managing Testflinger agent source code."""

import logging
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import psutil
from git import Repo

from common import run_with_logged_errors
from defaults import (
    DEFAULT_BRANCH,
    DEFAULT_TESTFLINGER_REPO,
    UV_BIN_PATH,
    VIRTUAL_ENV_PATH,
)

# Only keep these directories from the repo in the sparse checkout
TESTFLINGER_PACKAGES = ("agent", "common", "device-connectors")

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
    with tempfile.NamedTemporaryFile(
        dir=new_venv.parent, prefix="tmp_link_", delete=True
    ) as tmp:
        tmp_symlink = Path(tmp.name)
        # Close the file as we only need the name for the symlink
        tmp.close()
        tmp_symlink.symlink_to(new_venv)
        tmp_symlink.replace(venv_path)


def cleanup_old_virtualenvs():
    """Remove old virtualenvs that are no longer in use.

    A venv is considered safe to remove once all agents that could have
    been using it have restarted. For each old venv, the cutoff is the
    mtime of the next newer venv (when the next one was created, this one
    was superseded).
    """
    venv_path = Path(VIRTUAL_ENV_PATH)
    if not venv_path.is_symlink():
        return

    active_symlink = venv_path.resolve()

    # Find all old venvs that match the naming pattern
    # and are not the active one
    old_venvs = sorted(
        venv
        for venv in venv_path.parent.glob(f"{venv_path.name}-*")
        if venv.is_dir() and venv.resolve() != active_symlink
    )
    if not old_venvs:
        return

    # Determine the oldest running agent process and its create_time so we can
    # later identify which venv may still be in use
    oldest_agent = float("inf")
    for proc in psutil.process_iter(["cmdline", "create_time"]):
        try:
            cmdline = proc.info.get("cmdline") or []
            if any("testflinger-agent" in arg for arg in cmdline):
                oldest_agent = min(oldest_agent, proc.info["create_time"])
        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied,
            psutil.ZombieProcess,
        ):
            continue

    # The cutoff for each old venv is the modification time of the next newer
    # venv. For the most recently superseded venv, the symlink mtime is used
    # instead.
    cutoffs = [v.stat().st_mtime for v in old_venvs[1:]] + [
        venv_path.lstat().st_mtime
    ]
    for old_venv, cutoff in zip(old_venvs, cutoffs, strict=True):
        if oldest_agent < cutoff:
            logger.debug("Skipping in-use virtualenv: %s", old_venv)
            continue
        logger.info("Removing old virtualenv: %s", old_venv)
        shutil.rmtree(old_venv, ignore_errors=True)
