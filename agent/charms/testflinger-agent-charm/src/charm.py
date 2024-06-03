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
        self.framework.observe(self.on.install, self.on_install)
        self.framework.observe(self.on.config_changed, self.on_config_changed)
        self.framework.observe(self.on.start, self.on_start)
        self.framework.observe(self.on.remove, self.on_remove)
        self.framework.observe(self.on.update_action, self.on_update_action)
        self._stored.set_default(
            testflinger_repo="",
            testflinger_branch="",
            unit_path=(
                f"/etc/systemd/system/testflinger-agent-{self.app.name}"
                ".service"
            ),
            agent_path=f"/srv/testflinger-agent/{self.app.name}",
            venv_path=f"/srv/testflinger-agent/{self.app.name}/env",
        )

    def on_install(self, _):
        """Install hook"""
        self.unit.status = MaintenanceStatus("Installing dependencies")
        # Ensure we have a fresh agent dir to start with
        shutil.rmtree(self._stored.agent_path, ignore_errors=True)
        os.makedirs(self._stored.agent_path)
        os.makedirs("/home/ubuntu/testflinger", exist_ok=True)
        shutil.chown("/home/ubuntu/testflinger", "ubuntu", "ubuntu")

        self.install_apt_packages(
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
        self.run_with_logged_errors(
            ["python3", "-m", "virtualenv", f"{self._stored.venv_path}"],
        )
        self.render_systemd_unit()

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

    def on_start(self, _):
        """Start the service"""
        service_name = f"testflinger-agent-{self.app.name}"
        systemd.service_restart(service_name)
        self.unit.status = ActiveStatus()

    def on_remove(self, _):
        """Stop the service"""
        service_name = f"testflinger-agent-{self.app.name}"
        systemd.service_stop(service_name)
        # remove the old systemd unit file and agent directory
        try:
            os.unlink(self._stored.unit_path)
        except FileNotFoundError:
            logger.error(
                "No systemd unit file found when removing: %s",
                self._stored.unit_path,
            )
        systemd.daemon_reload()
        shutil.rmtree(self._stored.agent_path, ignore_errors=True)

    def check_update_repos_needed(self):
        """
        Determine if any config settings change which require
        an update to the git repos
        """
        update_needed = False
        repo = self.config.get("testflinger-repo")
        if repo != self._stored.testflinger_repo:
            self._stored.testflinger_repo = repo
            update_needed = True
        branch = self.config.get("testflinger-branch")
        if branch != self._stored.testflinger_branch:
            self._stored.testflinger_branch = branch
            update_needed = True
        if update_needed:
            self.update_repos()

    def update_repos(self):
        """Recreate the git repos and reinstall everything needed"""
        self.cleanup_agent_dirs()
        repo_path = f"{self._stored.agent_path}/testflinger"
        repo = Repo.clone_from(
            url=self._stored.testflinger_repo,
            branch=self._stored.testflinger_branch,
            to_path=repo_path,
            no_checkout=True,
            depth=1,
        )
        # do a sparse checkout of only agent and device-connectors
        repo.git.checkout(
            f"origin/{self._stored.testflinger_branch}",
            "--",
            "agent",
            "common",
            "device-connectors",
        )
        # Install the agent and device-connectors
        for dir in ("agent", "device-connectors"):
            self.run_with_logged_errors(
                [
                    f"{self._stored.venv_path}/bin/pip3",
                    "install",
                    "-I",
                    f"{repo_path}/{dir}",
                ]
            )

    def cleanup_agent_dirs(self):
        """Remove old agent dirs before checking out again"""
        dirs_to_remove = ("testflinger",)
        # Temporarily skip removing the following two things so that we
        # don't accidentally remove it from a job in progress. Add these
        # back after this version has deployed everywhere.
        #    "testflinger-agent",
        #    "snappy-device-agents",
        for dir in dirs_to_remove:
            shutil.rmtree(
                f"{self._stored.agent_path}/{dir}", ignore_errors=True
            )

    def signal_restart_agent(self):
        """Signal testflinger-agent to restart when it's not busy"""
        restart_file = PosixPath(
            f"/tmp/TESTFLINGER-DEVICE-RESTART-{self.app.name}"
        )
        if restart_file.exists():
            return
        restart_file.open(mode="w").close()
        shutil.chown(restart_file, "ubuntu", "ubuntu")

    def write_config_files(self):
        """Overwrite the config files if they were changed"""
        tf_agent_config_path = (
            f"{self._stored.agent_path}/testflinger-agent.conf"
        )
        tf_agent_config = self.read_resource("testflinger_agent_configfile")
        self.write_file(tf_agent_config_path, tf_agent_config)
        device_config_path = f"{self._stored.agent_path}/default.yaml"
        device_config = self.read_resource("device_configfile")
        self.write_file(device_config_path, device_config)

    def render_systemd_unit(self):
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

    def on_config_changed(self, _):
        self.unit.status = MaintenanceStatus("Handling config_changed hook")
        self.check_update_repos_needed()
        self.write_config_files()
        self.render_systemd_unit()
        self.signal_restart_agent()
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

    def on_update_action(self, event):
        """Force an update of git trees and config files"""
        self.unit.status = MaintenanceStatus("Handling update action")
        self.update_repos()
        self.write_config_files()
        self.signal_restart_agent()
        self.unit.status = ActiveStatus()


if __name__ == "__main__":
    main(TestflingerAgentCharm)
