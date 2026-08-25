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

    :param new_venv: The path to the new virtualenv.
    """
    # Attempt to create a temporary symlink and replace the existing symlink
    # Failures are bubbled up to the caller to handle.
    with tempfile.NamedTemporaryFile(
        dir=new_venv.parent, prefix="tmp_link_", delete=True
    ) as tmp:
        tmp_symlink = Path(tmp.name)
        # Close the file as we only need the name for the symlink
        tmp.close()
        tmp_symlink.symlink_to(new_venv)
        tmp_symlink.replace(Path(VIRTUAL_ENV_PATH))


def is_venv_in_use(venv_path: Path) -> bool:
    """Check if the virtualenv is currently in use by any process.

    :param venv_path: The path to the virtualenv.
    :return: True if the virtualenv is in use, False otherwise.
    """
    resolved_path = venv_path.resolve()
    for proc in psutil.process_iter(["pid", "exe", "open_files"]):
        try:
            # Check binary executable path
            if proc.info["exe"] and Path(
                proc.info["exe"]
            ).resolve().is_relative_to(resolved_path):
                return True

            # Check open file descriptors
            if proc.info["open_files"]:
                for open_file in proc.info["open_files"]:
                    if (
                        Path(open_file.path)
                        .resolve()
                        .is_relative_to(resolved_path)
                    ):
                        return True

            # Check memory-mapped files (e.g. .so libs loaded from the venv).
            for mmap in proc.memory_maps():
                if Path(mmap.path).resolve().is_relative_to(resolved_path):
                    return True

        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied,
            psutil.ZombieProcess,
        ):
            continue

    return False


def cleanup_old_virtualenvs():
    """Remove virtualenvs that are not currently in use.

    This skips the active virtualenv to prevent accidental deletion.
    """
    venv_path = Path(VIRTUAL_ENV_PATH)

    active_symlink = venv_path.resolve() if venv_path.is_symlink() else None

    pattern = f"{venv_path.name}-*"
    for old_venv in venv_path.parent.glob(pattern):
        if not old_venv.is_dir():
            continue

        # Skip the active virtualenv symlink
        if active_symlink and old_venv.resolve() == active_symlink:
            logger.debug("Skipping active virtualenv: %s", old_venv)
            continue

        # Check if the virtualenv is in use, if not, remove it
        if not is_venv_in_use(old_venv):
            logger.info("Removing old virtualenv: %s", old_venv)
            shutil.rmtree(old_venv, ignore_errors=True)
