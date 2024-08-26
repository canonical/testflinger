#!/usr/bin/env python3
# Copyright 2022 Canonical
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk


import logging
import os
import shutil
import sys
from pathlib import Path
from common import run_with_logged_errors
from git import Repo, GitCommandError
from jinja2 import Template

from charms.operator_libs_linux.v0 import apt
from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import (
    ActiveStatus,
    BlockedStatus,
    MaintenanceStatus,
    ModelError,
)
import testflinger_source
from defaults import AGENT_CONFIGS_PATH, LOCAL_TESTFLINGER_PATH

logger = logging.getLogger(__name__)


class TestflingerAgentHostCharm(CharmBase):
    """Base charm for testflinger agent host systems"""

    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.install, self.on_install)
        self.framework.observe(self.on.start, self.on_start)
        self.framework.observe(self.on.config_changed, self.on_config_changed)
        self.framework.observe(self.on.upgrade_charm, self.on_upgrade_charm)
        self.framework.observe(
            self.on.update_configs_action,
            self.on_update_configs_action,
        )
        self.framework.observe(
            self.on.update_testflinger_action,
            self.on_update_testflinger_action,
        )
        self._stored.set_default(
            ssh_priv="",
            ssh_pub="",
        )

    def on_install(self, _):
        """Install hook"""
        self.install_dependencies()
        self.setup_docker()
        self.update_tf_cmd_scripts()
        self.update_testflinger_repo()
        try:
            self.update_config_files()
        except ValueError:
            self.unit.status = BlockedStatus(
                "config-repo and config-dir must be set"
            )
            return

    def install_dependencies(self):
        """Install the packages needed for the agent"""
        self.unit.status = MaintenanceStatus("Installing dependencies")
        # maas cli comes from maas snap now
        run_with_logged_errors(["snap", "install", "maas"])

        self.install_apt_packages(
            [
                "python3-pip",
                "python3-virtualenv",
                "docker.io",
                "git",
                "openssh-client",
                "sshpass",
                "snmp",
            ]
        )

    def update_testflinger_repo(self):
        """Update the testflinger repo"""
        self.unit.status = MaintenanceStatus("Creating virtualenv")
        testflinger_source.create_virtualenv()
        self.unit.status = MaintenanceStatus("Cloning testflinger repo")
        testflinger_source.clone_repo(LOCAL_TESTFLINGER_PATH)

    def update_config_files(self):
        """
        Clone the config files from the repo and swap it in for whatever is
        in AGENT_CONFIGS_PATH
        """
        config_repo = self.config.get("config-repo")
        config_dir = self.config.get("config-dir")
        config_branch = self.config.get("config-branch")
        if not config_repo or not config_dir:
            logger.error("config-repo and config-dir must be set")
            raise ValueError("config-repo and config-dir must be set")
        tmp_repo_path = Path("/srv/tmp-agent-configs")
        repo_path = Path(AGENT_CONFIGS_PATH)
        if tmp_repo_path.exists():
            shutil.rmtree(tmp_repo_path, ignore_errors=True)
        try:
            Repo.clone_from(
                url=config_repo,
                branch=config_branch,
                to_path=tmp_repo_path,
                depth=1,
            )
        except GitCommandError:
            logger.exception("Failed to update config files")
            self.unit.status = BlockedStatus(
                "Failed to update or config files"
            )
            sys.exit(1)

        if repo_path.exists():
            shutil.rmtree(repo_path, ignore_errors=True)
        shutil.move(tmp_repo_path, repo_path)

    def setup_docker(self):
        run_with_logged_errors(["groupadd", "docker"])
        run_with_logged_errors(["gpasswd", "-a", "ubuntu", "docker"])

    def write_file(self, location, contents):
        # Sanity check to make sure we're actually about to write something
        if not contents:
            return
        with open(location, "w", encoding="utf-8", errors="ignore") as out:
            out.write(contents)

    def copy_ssh_keys(self):
        priv_key = self.config.get("ssh_private_key")
        if self._stored.ssh_priv != priv_key:
            self._stored.ssh_priv = priv_key
            self.write_file("/home/ubuntu/.ssh/id_rsa", priv_key)
        pub_key = self.config.get("ssh_public_key")
        if self._stored.ssh_pub != pub_key:
            self._stored.ssh_pub = pub_key
            self.write_file("/home/ubuntu/.ssh/id_rsa.pub", pub_key)

    def update_tf_cmd_scripts(self):
        """Update tf-cmd-scripts"""
        self.unit.status = MaintenanceStatus("Installing tf-cmd-scripts")
        tf_cmd_dir = "src/tf-cmd-scripts/"
        usr_local_bin = "/usr/local/bin/"
        for tf_cmd_file in os.listdir(tf_cmd_dir):
            shutil.copy(os.path.join(tf_cmd_dir, tf_cmd_file), usr_local_bin)
            os.chmod(os.path.join(usr_local_bin, tf_cmd_file), 0o775)

    def on_upgrade_charm(self, _):
        """Upgrade hook"""
        self.unit.status = MaintenanceStatus("Handling upgrade_charm hook")
        self.update_tf_cmd_scripts()
        self.unit.status = ActiveStatus()

    def on_start(self, _):
        """Start the service"""
        self.unit.status = ActiveStatus()

    def on_config_changed(self, _):
        self.unit.status = MaintenanceStatus("Handling config_changed hook")
        self.copy_ssh_keys()
        try:
            self.update_config_files()
        except ValueError:
            self.unit.status = BlockedStatus(
                "config-repo and config-dir must be set"
            )
            return
        self.unit.status = ActiveStatus()

    def install_apt_packages(self, packages: list):
        """Simple wrapper around 'apt-get install -y"""
        try:
            apt.update()
            apt.add_package(packages)
        except apt.PackageNotFoundError:
            logger.error(
                "a specified package not found in package cache or on system"
            )
            self.unit.status = BlockedStatus("Failed to install packages")
        except apt.PackageError:
            logger.error("could not install package")
            self.unit.status = BlockedStatus("Failed to install packages")

    def on_update_testflinger_action(self, event):
        """Update Testflinger agent code"""
        self.unit.status = MaintenanceStatus("Updating Testflinger Agent Code")
        self.update_testflinger_repo()
        self.unit.status = ActiveStatus()

    def on_update_configs_action(self, event):
        """Update agent configs"""
        self.unit.status = MaintenanceStatus(
            "Updating Testflinger Agent Configs"
        )
        try:
            self.update_config_files()
        except ValueError:
            self.unit.status = BlockedStatus(
                "config-repo and config-dir must be set"
            )
            return
        self.unit.status = ActiveStatus()


if __name__ == "__main__":
    main(TestflingerAgentHostCharm)
