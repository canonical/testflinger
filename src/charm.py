#!/usr/bin/env python3
# Copyright 2022 Canonical
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""Charm the service.

Refer to the following post for a quick-start guide that will help you
develop a new k8s charm using the Operator Framework:

    https://discourse.charmhub.io/t/4208
"""

import logging
import os
import shutil
import subprocess
from pathlib import PosixPath

from charms.operator_libs_linux.v0 import apt, systemd
from git import Repo
from jinja2 import Template
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


class TestflingerAgentCharm(CharmBase):
    """Charm the service."""

    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.remove, self._on_remove)
        self._stored.set_default(
            testflinger_agent_repo="",
            testflinger_agent_branch="",
            device_agent_repo="",
            device_agent_branch="",
            unit_path=(
                f"/etc/systemd/system/testflinger-agent-{self.app.name}"
                ".service"
            ),
            agent_path=f"/srv/testflinger-agent/{self.app.name}",
            venv_path=f"/srv/testflinger-agent/{self.app.name}/env",
        )

    def _on_install(self, _):
        """Install hook"""
        self.unit.status = MaintenanceStatus("Installing dependencies")
        # Ensure we have a fresh agent dir to start with
        shutil.rmtree(self._stored.agent_path, ignore_errors=True)
        os.makedirs(self._stored.agent_path)
        os.makedirs("/home/ubuntu/testflinger", exist_ok=True)
        shutil.chown("/home/ubuntu/testflinger", "ubuntu", "ubuntu")

        self._install_apt_packages(
            [
                "python3-pip",
                "python3-virtualenv",
                "openssh-client",
                "sshpass",
                "snmp",
                "git",
            ]
        )
        # Create the virtualenv
        self._run_with_logged_errors(
            ["python3", "-m", "virtualenv", f"{self._stored.venv_path}"],
        )
        self._render_systemd_unit()

    def _run_with_logged_errors(self, cmd):
        """Run a command, log output if errors, return proc just in case"""
        proc = subprocess.run(
            cmd, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, text=True
        )
        if proc.returncode:
            logger.error(proc.stdout)
        return proc

    def _write_file(self, location, contents):
        # Sanity check to make sure we're actually about to write something
        if not contents:
            return
        with open(location, "w", encoding="utf-8", errors="ignore") as out:
            out.write(contents)

    def _on_start(self, _):
        """Start the service"""
        service_name = f"testflinger-agent-{self.app.name}"
        systemd.service_restart(service_name)
        self.unit.status = ActiveStatus()

    def _on_remove(self, _):
        """Stop the service"""
        service_name = f"testflinger-agent-{self.app.name}"
        systemd.service_stop(service_name)
        # remove the old systemd unit file and agent directory
        try:
            os.unlink(self._stored.unit_path)
        except FileNotFoundError:
            logger.error("No systemd unit file found when removing: %s",
                         self._stored.unit_path)
        systemd.daemon_reload()
        shutil.rmtree(self._stored.agent_path, ignore_errors=True)

    def _check_update_repos_needed(self):
        """
        Determine if any config settings change which require
        an update to the git repos
        """
        update_repos = False
        repo = self.config.get("testflinger-agent-repo")
        if repo != self._stored.testflinger_agent_repo:
            self._stored.testflinger_agent_repo = repo
            update_repos = True
        branch = self.config.get("testflinger-agent-branch")
        if branch != self._stored.testflinger_agent_branch:
            self._stored.testflinger_agent_branch = branch
            update_repos = True
        repo = self.config.get("device-agent-repo")
        if repo != self._stored.device_agent_repo:
            self._stored.device_agent_repo = repo
            update_repos = True
        branch = self.config.get("device-agent-branch")
        if branch != self._stored.device_agent_branch:
            self._stored.device_agent_branch = branch
            update_repos = True
        if update_repos:
            self._update_repos()

    def _update_repos(self):
        """Recreate the git repos and reinstall everything needed"""
        tf_agent_dir = f"{self._stored.agent_path}/testflinger-agent"
        device_agent_dir = f"{self._stored.agent_path}/snappy-device-agents"
        shutil.rmtree(tf_agent_dir, ignore_errors=True)
        shutil.rmtree(device_agent_dir, ignore_errors=True)
        Repo.clone_from(
            self._stored.testflinger_agent_repo,
            tf_agent_dir,
            multi_options=[f"-b {self._stored.testflinger_agent_branch}"],
        )
        self._run_with_logged_errors(
            [f"{self._stored.venv_path}/bin/pip3", "install", "-I",
             tf_agent_dir]
        )
        Repo.clone_from(
            self._stored.device_agent_repo,
            device_agent_dir,
            multi_options=[f"-b {self._stored.device_agent_branch}"],
        )
        self._run_with_logged_errors(
            [f"{self._stored.venv_path}/bin/pip3", "install", "-I",
             device_agent_dir]
        )

    def _signal_restart_agent(self):
        """Signal testflinger-agent to restart when it's not busy"""
        restart_file = f"/tmp/TESTFLINGER-DEVICE-RESTART-{self.app.name}"
        open(restart_file, mode="w").close()
        shutil.chown(restart_file, "ubuntu", "ubuntu")

    def _write_config_files(self):
        """Overwrite the config files if they were changed"""
        tf_agent_config_path = (
            f"{self._stored.agent_path}/testflinger-agent/"
            "testflinger-agent.conf"
        )
        tf_agent_config = self._read_resource("testflinger_agent_configfile")
        self._write_file(tf_agent_config_path, tf_agent_config)
        device_config_path = (
            f"{self._stored.agent_path}/" "snappy-device-agents/default.yaml"
        )
        device_config = self._read_resource("testflinger_agent_configfile")
        self._write_file(device_config_path, device_config)

    def _render_systemd_unit(self):
        """Render the systemd unit for Gunicorn to a file"""
        # Open the template systemd unit file
        with open(
            "templates/testflinger-agent.service.j2",
            "r",
            encoding="utf-8",
            errors="ignore",
        ) as service_template:
            template = Template(service_template.read())

        # Render the template files with the correct values
        rendered = template.render(
            project_root=self._stored.agent_path,
        )
        # Write the rendered file out to disk
        with open(
            self._stored.unit_path, "w+", encoding="utf-8", errors="ignore"
        ) as systemd_file:
            systemd_file.write(rendered)

        # Ensure correct permissions are set on the service
        os.chmod(self._stored.unit_path, 0o755)
        # Reload systemd units
        systemd.daemon_reload()

    def _on_config_changed(self, _):
        self.unit.status = MaintenanceStatus("Handling config_changed hook")
        self._check_update_repos_needed()
        self._write_config_files()
        self._signal_restart_agent()
        self.unit.status = ActiveStatus()

    def _install_apt_packages(self, packages: list):
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

    def _read_resource(self, resource):
        """Read the specified resource and return the contents"""
        try:
            resource_file = self.model.resources.fetch(resource)
        except ModelError:
            # resource doesn't exist yet, return empty string
            return ""
        if (
            not isinstance(resource_file, PosixPath) or not
            resource_file.exists()
        ):
            # Return empty string if it's invalid
            return ""
        with open(resource_file, encoding="utf-8", errors="ignore") as res:
            contents = res.read()
        return contents


if __name__ == "__main__":
    main(TestflingerAgentCharm)
