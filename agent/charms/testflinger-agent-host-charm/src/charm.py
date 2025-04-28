#!/usr/bin/env python3
# Copyright 2022 Canonical
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk


import logging
import os
import shutil
import sys
from base64 import b64decode
from pathlib import Path

import testflinger_source
from common import run_with_logged_errors
from defaults import (
    AGENT_CONFIGS_PATH,
    LOCAL_TESTFLINGER_PATH,
    VIRTUAL_ENV_PATH,
)
from git import GitCommandError, Repo
from jinja2 import Template
from ops.charm import CharmBase
from ops.main import main
from ops.model import (
    ActiveStatus,
    BlockedStatus,
    MaintenanceStatus,
)

from charms.operator_libs_linux.v0 import apt

logger = logging.getLogger(__name__)


class TestflingerAgentHostCharm(CharmBase):
    """Base charm for testflinger agent host systems."""

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

    def on_install(self, _):
        """Install hook."""
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
        """Install the packages needed for the agent."""
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
                "supervisor",
            ]
        )

    def update_testflinger_repo(self, branch=None):
        """Update the testflinger repo."""
        self.unit.status = MaintenanceStatus("Creating virtualenv")
        testflinger_source.create_virtualenv()
        self.unit.status = MaintenanceStatus("Cloning testflinger repo")
        if branch is not None:
            testflinger_source.clone_repo(
                LOCAL_TESTFLINGER_PATH, branch=branch
            )
        else:
            testflinger_source.clone_repo(LOCAL_TESTFLINGER_PATH)

    def update_config_files(self):
        """
        Clone the config files from the repo and swap it in for whatever is
        in AGENT_CONFIGS_PATH.
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

    def write_supervisor_service_files(self):
        """
        Generate supervisord service files for all agents.

        We assume that the path pointed to by the config-dir config option
        contains a directory for each agent that needs to run from this host.
        The agent directory name will be used as the service name.
        """
        config_dirs = Path(AGENT_CONFIGS_PATH) / self.config.get("config-dir")

        if not config_dirs.is_dir():
            logger.error("config-dir must point to a directory")
            self.unit.status = BlockedStatus(
                "config-dir must point to a directory"
            )
            sys.exit(1)

        agent_dirs = [
            directory
            for directory in config_dirs.iterdir()
            if directory.is_dir()
        ]
        if not agent_dirs:
            logger.error("No agent directories found in config-dirs")
            self.unit.status = BlockedStatus(
                "No agent directories found in config-dirs"
            )
            sys.exit(1)

        # Remove all the old service files in case agents have been removed
        for conf_file in os.listdir("/etc/supervisor/conf.d"):
            if conf_file.endswith(".conf"):
                os.unlink(f"/etc/supervisor/conf.d/{conf_file}")

        # now write the supervisord service files
        with open(
            "templates/testflinger-agent.supervisord.conf.j2", "r"
        ) as service_template:
            template = Template(service_template.read())
        for agent_dir in agent_dirs:
            agent_config_path = agent_dir
            rendered = template.render(
                agent_name=agent_dir.name,
                agent_config_path=agent_config_path,
                virtual_env_path=VIRTUAL_ENV_PATH,
            )
            with open(
                f"/etc/supervisor/conf.d/{agent_dir.name}.conf", "w"
            ) as agent_file:
                agent_file.write(rendered)

    def supervisor_update(self):
        """
        Once supervisord service files have been written, new agents will be
        automatically started, and missing agents will be removed by running
        `supervisorctl update`. This only applies to supervisor conf files
        that have changed. So any agents for which the conf file has not
        changed will be unaffected.
        """
        run_with_logged_errors(["supervisorctl", "update"])

    def restart_agents(self):
        """
        Mark all agents as needing a restart when they are not running a job
        so that they read any updated config files and run the latest
        version of the agent code.
        """
        run_with_logged_errors(["supervisorctl", "signal", "USR1", "all"])

    def setup_docker(self):
        run_with_logged_errors(["groupadd", "docker"])
        run_with_logged_errors(["gpasswd", "-a", "ubuntu", "docker"])

    def write_file(self, location, contents):
        with open(location, "w", encoding="utf-8", errors="ignore") as out:
            out.write(contents)

    def copy_ssh_keys(self):
        try:
            ssh_config = self.config.get("ssh-config")
            self.write_file("/home/ubuntu/.ssh/config", ssh_config)
            os.chown("/home/ubuntu/.ssh/config", 1000, 1000)
            os.chmod("/home/ubuntu/.ssh/config", 0o640)

            priv_key = self.config.get("ssh-private-key", "")
            self.write_file(
                "/home/ubuntu/.ssh/id_rsa", b64decode(priv_key).decode()
            )
            os.chown("/home/ubuntu/.ssh/id_rsa", 1000, 1000)
            os.chmod("/home/ubuntu/.ssh/id_rsa", 0o600)

            pub_key = self.config.get("ssh-public-key", "")
            self.write_file(
                "/home/ubuntu/.ssh/id_rsa.pub", b64decode(pub_key).decode()
            )
            os.chown("/home/ubuntu/.ssh/id_rsa.pub", 1000, 1000)
        except (TypeError, UnicodeDecodeError):
            logger.error(
                "Failed to decode ssh keys - ensure they are base64 encoded"
            )
            raise

    def update_tf_cmd_scripts(self):
        """Update tf-cmd-scripts."""
        self.unit.status = MaintenanceStatus("Installing tf-cmd-scripts")
        tf_cmd_dir = "src/tf-cmd-scripts/"
        usr_local_bin = Path("/usr/local/bin")

        for tf_cmd_file in os.listdir(tf_cmd_dir):
            template = Template(
                open(os.path.join(tf_cmd_dir, tf_cmd_file)).read()
            )
            rendered = template.render(
                agent_configs_path=AGENT_CONFIGS_PATH,
                config_dir=self.config.get("config-dir"),
                virtual_env_path=VIRTUAL_ENV_PATH,
            )
            agent_file = usr_local_bin / tf_cmd_file
            agent_file.write_text(rendered)
            agent_file.chmod(0o775)

    def on_upgrade_charm(self, _):
        """Upgrade hook."""
        self.unit.status = MaintenanceStatus("Handling upgrade_charm hook")
        self.update_tf_cmd_scripts()
        self.unit.status = ActiveStatus()

    def on_start(self, _):
        """Start the service."""
        self.unit.status = ActiveStatus()

    def on_config_changed(self, _):
        self.unit.status = MaintenanceStatus("Handling config_changed hook")
        try:
            self.update_config_files()
        except ValueError:
            self.unit.status = BlockedStatus(
                "config-repo and config-dir must be set"
            )
            return
        self.copy_ssh_keys()
        self.write_supervisor_service_files()
        self.supervisor_update()
        self.restart_agents()
        self.unit.status = ActiveStatus()

    def install_apt_packages(self, packages: list):
        """Wrap 'apt-get install -y."""
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
        """Update Testflinger agent code."""
        self.unit.status = MaintenanceStatus("Updating Testflinger Agent Code")
        branch = event.params.get("branch")
        self.update_testflinger_repo(branch)
        self.restart_agents()
        self.unit.status = ActiveStatus()

    def on_update_configs_action(self, event):
        """Update agent configs."""
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
        self.write_supervisor_service_files()
        self.supervisor_update()
        self.restart_agents()
        self.unit.status = ActiveStatus()


if __name__ == "__main__":
    main(TestflingerAgentHostCharm)
