# Copyright 2024 Canonical
# See LICENSE file for licensing details.
"""Module for managing Testflinger agent source code."""

import logging
import shutil
import tempfile
from pathlib import Path

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


def create_virtualenv(local_path: str):
    """Build a virtualenv and install the Testflinger packages into it.

    The virtualenv is built in a temporary directory and then swapped into
    place to avoid disrupting any agents that are currently running.

    :param local_path: The local path where the Testflinger repo is located.
    """
    venv_path = Path(VIRTUAL_ENV_PATH)

    # Create a temporary directory in the same parent folder
    # This ensures that the rename operation is atomic
    tmp_dir = Path(tempfile.mkdtemp(dir=venv_path.parent, prefix="tmp_venv_"))
    old_venv_backup = venv_path.with_name(f"{venv_path.name}.old")

    try:
        # Initialize the temporary virtualenv
        run_with_logged_errors([UV_BIN_PATH, "venv", str(tmp_dir)])

        # Install the testflinger packages into the temporary virtualenv
        for tf_package in TESTFLINGER_PACKAGES:
            logger.debug("Installing Python package: %s", tf_package)
            run_with_logged_errors(
                [
                    UV_BIN_PATH,
                    "pip",
                    "install",
                    "--python",
                    f"{tmp_dir}/bin/python3",
                    "-U",
                    f"{local_path}/{tf_package}",
                ]
            )

        # Remove any leftover backup from the previous upgrade.
        shutil.rmtree(old_venv_backup, ignore_errors=True)

        # Track states for safe cleanup
        moved_old = False
        swap_successful = False
        try:
            if venv_path.exists():
                venv_path.rename(old_venv_backup)
                moved_old = True

            tmp_dir.rename(venv_path)
            swap_successful = True

        except OSError as exc:
            logger.error("Failed to replace virtualenv: %s", exc)
            if moved_old:
                try:
                    old_venv_backup.rename(venv_path)
                except OSError as restore_exc:
                    logger.error(
                        "Failed to restore old virtualenv: %s", restore_exc
                    )
                    logger.error(
                        "Old virtualenv may be recovered from: %s",
                        old_venv_backup,
                    )

    finally:
        # Only clean up tmp_dir if the swap failed.
        # If swap was successful, tmp_dir no longer exists at its old path.
        if not swap_successful:
            shutil.rmtree(tmp_dir, ignore_errors=True)
