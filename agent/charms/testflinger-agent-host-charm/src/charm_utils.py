# Copyright 2026 Canonical
# See LICENSE file for licensing details.
"""Utility functions for the Testflinger Agent Host charm."""

import logging
import shutil
from pathlib import Path

from charmlibs import apt, passwd
from git import GitCommandError, Repo

from common import run_with_logged_errors
from config import TestflingerAgentConfig
from defaults import AGENT_CONFIGS_PATH, TESTENV_IMAGE

logger = logging.getLogger(__name__)

AGENT_PACKAGES = [
    "python3-pip",
    "python3-virtualenv",
    "pipx",
    "docker.io",
    "git",
    "openssh-client",
    "sshpass",
    "snmp",
    "supervisor",
]

CHARM_USER = "ubuntu"
DOCKER_GROUP = "docker"


def install_agent_packages() -> None:
    """Install necessary packages for the agents."""
    apt.update()
    apt.add_package(AGENT_PACKAGES)


def setup_docker():
    """Set up docker group and add charm user to the docker group."""
    passwd.add_group(DOCKER_GROUP)
    passwd.add_user_to_group(CHARM_USER, DOCKER_GROUP)


def update_config_files(config: TestflingerAgentConfig):
    """Update the agent configuration files.

    Clone the config files from the repo and swap it in for whatever is
    in AGENT_CONFIGS_PATH.
    """
    tmp_repo_path = Path("/srv/tmp-agent-configs")
    repo_path = Path(AGENT_CONFIGS_PATH)
    if tmp_repo_path.exists():
        shutil.rmtree(tmp_repo_path)
    try:
        Repo.clone_from(
            url=config.config_repo,
            branch=config.config_branch,
            to_path=tmp_repo_path,
            depth=1,
        )
    except GitCommandError as err:
        logger.error("Failed to update config files: %s", err)
        raise RuntimeError("Failed to update or config files") from err
    if repo_path.exists():
        shutil.rmtree(repo_path)
    shutil.move(tmp_repo_path, repo_path)


def pull_container_latest(container_tag: str) -> bool:
    """Pull the latest testenv image for the given tag.

    :param container_tag: The testenv image tag (e.g. jammy, noble).
    :returns: True if the pull succeeded, False otherwise.
    """
    image = f"{TESTENV_IMAGE}:{container_tag}"
    logger.info("Pulling latest container image: %s", image)
    return run_with_logged_errors(["docker", "pull", image]) == 0
