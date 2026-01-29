# Copyright 2024 Canonical
# See LICENSE file for licensing details.

import logging
import os
import subprocess
from base64 import b64decode
from pathlib import Path

from defaults import (
    AGENT_CONFIGS_PATH,
    VIRTUAL_ENV_PATH,
)
from jinja2 import Template

logger = logging.getLogger(__name__)

SSH_CONFIG = "/home/ubuntu/.ssh/config"
SSH_PUBLIC_KEY = "/home/ubuntu/.ssh/id_rsa.pub"
SSH_PRIVATE_KEY = "/home/ubuntu/.ssh/id_rsa"


def run_with_logged_errors(cmd: list) -> int:
    """Run a command, log output if errors, return exit code."""
    proc = subprocess.run(  # noqa: S603
        cmd,
        stderr=subprocess.STDOUT,
        stdout=subprocess.PIPE,
        text=True,
        check=False,
    )
    if proc.returncode:
        logger.error(proc.stdout)
    return proc.returncode


def copy_ssh_keys(config: dict) -> None:
    try:
        ssh_config = config.get("ssh-config", "")
        config_file = Path(SSH_CONFIG)
        write_file(config_file, ssh_config, chmod=0o640)

        priv_key = config.get("ssh-private-key", "")
        priv_key_file = Path(SSH_PRIVATE_KEY)
        write_file(priv_key_file, b64decode(priv_key).decode(), chmod=0o600)

        pub_key = config.get("ssh-public-key", "")
        pub_key_file = Path(SSH_PUBLIC_KEY)
        write_file(pub_key_file, b64decode(pub_key).decode())
    except (TypeError, UnicodeDecodeError):
        logger.error(
            "Failed to decode ssh keys - ensure they are base64 encoded"
        )
        raise


def write_file(location: Path, contents: str, chmod: int = 0o644) -> None:
    """Write contents to a file at location with specified permissions.

    This also sets the owner to user/group 1000:1000 (ubuntu:ubuntu).

    :param location: Path to the file to write.
    :param contents: Contents to write to the file.
    :param chmod: File permission to set on the file.
    """
    with open(location, "w", encoding="utf-8", errors="ignore") as out:
        out.write(contents)
    os.chown(location, 1000, 1000)
    os.chmod(location, chmod)


def update_charm_scripts(config: dict) -> None:
    tf_cmd_dir = Path("src/tf-cmd-scripts/")
    usr_local_bin = Path("/usr/local/bin")

    for tf_cmd_file in tf_cmd_dir.iterdir():
        template = Template(tf_cmd_file.read_text())
        rendered = template.render(
            agent_configs_path=AGENT_CONFIGS_PATH,
            config_dir=config.get("config-dir"),
            virtual_env_path=VIRTUAL_ENV_PATH,
        )
        agent_file = usr_local_bin / tf_cmd_file.name
        agent_file.write_text(rendered)
        agent_file.chmod(0o775)
