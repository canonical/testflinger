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

import ops
import supervisord
import testflinger_source
from charmlibs import apt, passwd
from charms.grafana_agent.v0.cos_agent import COSAgentProvider
from common import copy_ssh_keys, run_with_logged_errors, update_charm_scripts
from defaults import (
    AGENT_CONFIGS_PATH,
    LOCAL_TESTFLINGER_PATH,
    VIRTUAL_ENV_PATH,
)
from git import GitCommandError, Repo
from jinja2 import Template
from testflinger_client import authenticate, token_update_needed

logger = logging.getLogger(__name__)

SUPERVISOR_CONF_DIR = "/etc/supervisor/conf.d"


class TestflingerAgentHostCharm(ops.charm.CharmBase):
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
        self.scrape_jobs = []
        self._grafana_agent = COSAgentProvider(
            self,
            scrape_configs=self.get_scrape_jobs,
        )
        self.framework.observe(self.on.secret_changed, self._on_secret_changed)
        self.framework.observe(self.on.update_status, self._on_update_status)

    def on_install(self, _):
        """Install hook."""
        self.install_dependencies()
        self.setup_docker()
        self.update_tf_cmd_scripts()
        self.update_testflinger_repo()
        try:
            self.update_config_files()
        except ValueError:
            self.unit.status = ops.model.BlockedStatus(
                "config-repo and config-dir must be set"
            )
            return

    def install_dependencies(self):
        """Install the packages needed for the agent."""
        self.unit.status = ops.model.MaintenanceStatus(
            "Installing dependencies"
        )
        # maas cli comes from maas snap now
        run_with_logged_errors(["snap", "install", "maas"])

        self.install_apt_packages(
            [
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
        )
        run_with_logged_errors(["pipx", "install", "uv"])

    def update_testflinger_repo(self, branch: str | None = None):
        """Update the testflinger repo."""
        self.unit.status = ops.model.MaintenanceStatus("Creating virtualenv")
        testflinger_source.create_virtualenv()
        self.unit.status = ops.model.MaintenanceStatus(
            "Cloning testflinger repo"
        )
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
            self.unit.status = ops.model.BlockedStatus(
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
            self.unit.status = ops.model.BlockedStatus(
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
            self.unit.status = ops.model.BlockedStatus(
                "No agent directories found in config-dirs"
            )
            sys.exit(1)

        # Get current agents and their ports from the service files
        configured_agents = supervisord.get_supervisor_agents_port_mapping()
        used_ports = set(configured_agents.values())
        logger.info(
            "Found %d configured agents",
            len(configured_agents),
        )

        # Remove all the old service files in case agents have been removed
        for conf_file in os.listdir(SUPERVISOR_CONF_DIR):
            if conf_file.endswith(".conf"):
                os.unlink(f"{SUPERVISOR_CONF_DIR}/{conf_file}")

        # now write the supervisord service files
        with open(
            "templates/testflinger-agent.supervisord.conf.j2", "r"
        ) as service_template:
            template = Template(service_template.read())

        self.scrape_jobs = []
        for agent_dir in agent_dirs:
            agent_config_path = agent_dir
            agent_name = agent_dir.name

            try:
                metric_endpoint_port = supervisord.assign_metrics_port(
                    agent_name, configured_agents, used_ports
                )
                used_ports.add(metric_endpoint_port)
            except RuntimeError as e:
                logger.error("Failed to assign port for %s: %s", agent_name, e)
                self.unit.status = ops.model.BlockedStatus(
                    f"Port assignment failed: {e}"
                )
                return

            rendered = template.render(
                agent_name=agent_name,
                agent_config_path=agent_config_path,
                virtual_env_path=VIRTUAL_ENV_PATH,
                metric_endpoint_port=metric_endpoint_port,
            )
            self.scrape_jobs.append(
                {
                    "job_name": agent_name,
                    "metrics_path": "/metrics",
                    "static_configs": [
                        {"targets": [f"localhost:{metric_endpoint_port}"]}
                    ],
                }
            )

            with open(
                f"{SUPERVISOR_CONF_DIR}/{agent_name}.conf", "w"
            ) as agent_file:
                agent_file.write(rendered)

    def setup_docker(self):
        passwd.add_group("docker")
        passwd.add_user_to_group("ubuntu", "docker")

    def update_tf_cmd_scripts(self):
        """Update tf-cmd-scripts."""
        self.unit.status = ops.model.MaintenanceStatus(
            "Installing tf-cmd-scripts"
        )
        update_charm_scripts(self.config)

    def on_upgrade_charm(self, _):
        """Upgrade hook."""
        self.unit.status = ops.model.MaintenanceStatus(
            "Handling upgrade_charm hook"
        )
        self.install_dependencies()
        self.update_tf_cmd_scripts()
        self.update_testflinger_repo()
        self.unit.status = ops.model.ActiveStatus()

    def on_start(self, _):
        """Start the service."""
        if not self._authenticate_with_server():
            return
        self.unit.status = ops.model.ActiveStatus()

    def _on_secret_changed(self, event: ops.SecretChangedEvent):
        """Handle secret changed event."""
        if event.secret.id == self.config.get("credentials-secret"):
            logger.info("Credentials secret changed, re-authenticating")
            self._authenticate_with_server()

    def _on_update_status(self, _):
        """Periodically check token expiration and re-authenticate if needed.

        By default, Juju triggers this event every 5 minutes.
        """
        if not self._authenticate_with_server():
            return
        self.unit.status = ops.model.ActiveStatus()

    def _block(self, message: str) -> bool:
        """Set unit to BlockedStatus and return False."""
        self.unit.status = ops.model.BlockedStatus(message)
        return False

    def _valid_secret(self) -> dict | None:
        """Check if the secret contains the necessary fields."""
        secret_uri = self.config.get("credentials-secret")
        if not secret_uri:
            logger.error("credentials-secret config not set")
            return

        try:
            secret = self.model.get_secret(id=secret_uri)
            content = secret.get_content(refresh=True)
            if "client_id" not in content or "secret_key" not in content:
                logger.error("Secret missing required fields")
                return
        except (ops.SecretNotFoundError, ops.ModelError):
            logger.error(
                "Credentials secret not found or inaccessible for the charm"
            )
            return

        return content

    def _authenticate_with_server(self) -> bool:
        """Authenticate with the server if token is missing or expiring.

        :returns: True if authentication succeeded or token is valid,
        False otherwise
        """
        if not token_update_needed():
            return True

        if not (content := self._valid_secret()):
            return self._block("Invalid credentials secret")

        server = self.config.get("testflinger-server")
        if not server or not server.startswith("http"):
            return self._block("Testflinger server config not set or invalid")

        logger.info("Authenticating with Testflinger server")
        if not authenticate(
            server=server,
            client_id=content["client_id"],
            secret_key=content["secret_key"],
        ):
            return self._block("Authentication with Testflinger server failed")

        return True

    def on_config_changed(self, _):
        self.unit.status = ops.model.MaintenanceStatus(
            "Handling config_changed hook"
        )
        try:
            self.update_config_files()
        except ValueError:
            self.unit.status = ops.model.BlockedStatus(
                "config-repo and config-dir must be set"
            )
            return
        copy_ssh_keys(self.config)
        self.update_tf_cmd_scripts()
        self._authenticate_with_server()
        self.write_supervisor_service_files()
        supervisord.supervisor_update()
        supervisord.restart_agents()
        self.unit.status = ops.model.ActiveStatus()

    def install_apt_packages(self, packages: list):
        """Wrap 'apt-get install -y."""
        try:
            apt.update()
            apt.add_package(packages)
        except apt.PackageNotFoundError:
            logger.error(
                "a specified package not found in package cache or on system"
            )
            self.unit.status = ops.model.BlockedStatus(
                "Failed to install packages"
            )
        except apt.PackageError:
            logger.error("could not install package")
            self.unit.status = ops.model.BlockedStatus(
                "Failed to install packages"
            )

    def on_update_testflinger_action(self, event: ops.ActionEvent):
        """Update Testflinger agent code."""
        self.unit.status = ops.model.MaintenanceStatus(
            "Updating Testflinger Agent Code"
        )
        branch = event.params.get("branch")
        self.update_testflinger_repo(branch)
        supervisord.restart_agents()
        self.unit.status = ops.model.ActiveStatus()

    def on_update_configs_action(self, event: ops.ActionEvent):
        """Update agent configs."""
        self.unit.status = ops.model.MaintenanceStatus(
            "Updating Testflinger Agent Configs"
        )
        try:
            self.update_config_files()
        except ValueError:
            self.unit.status = ops.model.BlockedStatus(
                "config-repo and config-dir must be set"
            )
            return
        self.write_supervisor_service_files()
        supervisord.supervisor_update()
        supervisord.restart_agents()
        self.unit.status = ops.model.ActiveStatus()

    def get_scrape_jobs(self):
        return self.scrape_jobs


if __name__ == "__main__":
    ops.main(TestflingerAgentHostCharm)
