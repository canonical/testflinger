#!/usr/bin/env python3
# Copyright 2022 Canonical
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk


import logging
import subprocess
import shutil
import os
from pathlib import Path, PosixPath

from charms.operator_libs_linux.v0 import apt, systemd
from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import (
    ActiveStatus,
    BlockedStatus,
    MaintenanceStatus,
    ModelError,
)

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
        self._stored.set_default(
            ssh_priv="",
            ssh_pub="",
        )

    def on_install(self, _):
        """Install hook"""
        self.unit.status = MaintenanceStatus("Installing dependencies")
        self.install_apt_packages(
            ["python3-pip", "python3-virtualenv", "docker.io"]
        )
        # maas cli comes from maas snap now
        self.run_with_logged_errors(["snap", "install", "maas"])
        self.setup_docker()
        self.update_tf_cmd_scripts()

    def setup_docker(self):
        self.run_with_logged_errors(["groupadd", "docker"])
        self.run_with_logged_errors(["gpasswd", "-a", "ubuntu", "docker"])

    def run_with_logged_errors(self, cmd):
        """Run a command, log output if errors, return proc just in case"""
        proc = subprocess.run(
            cmd, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, text=True
        )
        if proc.returncode:
            logger.error(proc.stdout)
        return proc

    def write_file(self, location, contents):
        # Sanity check to make sure we're actually about to write something
        if not contents:
            return
        with open(location, "w", encoding="utf-8", errors="ignore") as out:
            out.write(contents)

    def copy_ssh_keys(self):
        priv_key = self.read_resource("ssh_priv_key")
        if self._stored.ssh_priv != priv_key:
            self._stored.ssh_priv = priv_key
            self.write_file("/home/ubuntu/.ssh/id_rsa", priv_key)
        pub_key = self.read_resource("ssh_pub_key")
        if self._stored.ssh_pub != pub_key:
            self._stored.ssh_pub = pub_key
            self.write_file("/home/ubuntu/.ssh/id_rsa.pub", pub_key)

    def update_tf_cmd_scripts(self):
        """Update tf_cmd_scfipts"""
        tf_cmd_dir = "src/tf-cmd-scripts/"
        usr_local_bin = "/usr/local/bin/"
        for file in os.listdir(usr_local_bin):
            if "tf" in file:
                os.remove(os.path.join(usr_local_bin, file))
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

    def read_resource(self, resource):
        """Read the specified resource and return the contents"""
        try:
            resource_file = self.model.resources.fetch(resource)
        except ModelError:
            # resource doesn't exist yet, return empty string
            return ""
        if (
            not isinstance(resource_file, PosixPath)
            or not resource_file.exists()
        ):
            # Return empty string if it's invalid
            return ""
        with open(resource_file, encoding="utf-8", errors="ignore") as res:
            contents = res.read()
        return contents


if __name__ == "__main__":
    main(TestflingerAgentHostCharm)
