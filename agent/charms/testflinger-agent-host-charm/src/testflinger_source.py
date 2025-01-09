# Copyright 2024 Canonical
# See LICENSE file for licensing details.

import os
import shutil
from git import Repo
from common import run_with_logged_errors
from defaults import DEFAULT_TESTFLINGER_REPO, DEFAULT_BRANCH, VIRTUAL_ENV_PATH


# Only keep these directories from the repo in the sparse checkout
CHECKOUT_DIRS = ("agent", "common", "device-connectors")


def clone_repo(
    local_path,
    testflinger_repo=DEFAULT_TESTFLINGER_REPO,
    branch=DEFAULT_BRANCH,
):
    """Recreate the git repos and reinstall everything needed"""

    # First, remove the old repo
    shutil.rmtree(local_path, ignore_errors=True)

    # Clone the repo
    repo = Repo.clone_from(
        url=testflinger_repo,
        branch=branch,
        to_path=local_path,
        no_checkout=True,
        depth=1,
    )

    # do a sparse checkout of only the parts of the repo we need
    repo.git.checkout(
        f"origin/{branch}",
        "--",
        *CHECKOUT_DIRS,
    )
    for dir in (
        "agent",
        "device-connectors",
    ):
        run_with_logged_errors(
            [
                f"{VIRTUAL_ENV_PATH}/bin/pip3",
                "install",
                "-I",
                f"{local_path}/{dir}",
            ]
        )


def create_virtualenv():
    """Create a virtualenv for the agent unless one already exists"""
    if os.path.exists(VIRTUAL_ENV_PATH):
        return

    run_with_logged_errors(
        [
            "python3",
            "-m",
            "virtualenv",
            VIRTUAL_ENV_PATH,
        ]
    )

    # Update pip in the virtualenv so that poetry works in focal
    run_with_logged_errors(
        [
            f"{VIRTUAL_ENV_PATH}/bin/pip3",
            "install",
            "-U",
            "pip",
        ]
    )
