# Copyright (C) 2024 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Package containing modules for implementing Zapper-driven device connectors.

Modules inheriting from the provided abstract class will run Zapper-driven
provisioning procedures via Zapper API. The provisioning logic is implemented
in the Zapper codebase and the connector serves as a pre-processing step,
validating the configuration and preparing the API arguments.
"""

import json
import logging
import subprocess
from abc import ABC, abstractmethod
from typing import Any, Dict, Tuple

import rpyc

from testflinger_device_connectors.devices import (
    DefaultDevice,
    ProvisioningError,
)

logger = logging.getLogger(__name__)


class ZapperConnector(ABC, DefaultDevice):
    """Abstract base class defining a common interface for Zapper-driven
    device connectors.
    """

    PROVISION_METHOD = ""  # to be defined in the implementation
    ZAPPER_REQUEST_TIMEOUT = 60 * 90
    ZAPPER_SERVICE_PORT = 60000

    @staticmethod
    def _check_rpyc_server_on_host(host: str) -> None:
        """
        Check if the host has an active RPyC server running.

        :raises ConnectionError in case the server is not reachable.
        """
        timeout = 3
        try:
            subprocess.run(
                [
                    "/usr/bin/nc",
                    "-z",
                    "-w",
                    str(timeout),
                    host,
                    str(ZapperConnector.ZAPPER_SERVICE_PORT),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            logger.debug("The host %s has an available RPyC server", host)
        except subprocess.CalledProcessError as e:
            raise ConnectionError from e

    @staticmethod
    def wait_ready(host: str, timeout: int = 60) -> None:
        """Wait for an RPyC server to become available on the given host.

        :param host: The host to check for RPyC availability.
        :param timeout: Maximum time to wait in seconds (default: 60).
        :raises TimeoutError: If the server is not available within the timeout
        """
        logger.info(
            "Waiting for a running RPyC server on control host %s", host
        )
        DefaultDevice.wait_online(
            ZapperConnector._check_rpyc_server_on_host, host, timeout
        )

    @staticmethod
    def typecmux_set_state(host: str, state: str) -> None:
        """Connect to a Zapper host via RPyC and set the typecmux state.

        :param host: The Zapper host to connect to.
        :param state: The state to set (e.g., "OFF", "DUT").
        """
        connection = rpyc.connect(
            host,
            ZapperConnector.ZAPPER_SERVICE_PORT,
            config={
                "allow_public_attrs": True,
                "sync_request_timeout": 60,
            },
        )
        connection.root.typecmux_set_state(alias="default", state=state)
        logger.info("Set typecmux state to %s on %s", state, host)

    def provision(self, args):
        """Provision device when the command is invoked."""
        super().provision(args)

        control_host = self.config["control_host"]
        try:
            ZapperConnector.wait_ready(control_host)
        except TimeoutError as e:
            raise ProvisioningError(
                "Cannot reach out the Zapper service over RPyC"
            ) from e

        with open(args.job_data, encoding="utf-8") as job_json:
            self.job_data = json.load(job_json)

        logger.info("BEGIN provision")
        logger.info("Provisioning device")
        self.ZAPPER_REQUEST_TIMEOUT = self.job_data["provision_data"].get(
            "zapper_provisioning_timeout",
            self.ZAPPER_REQUEST_TIMEOUT,
        )

        (api_args, api_kwargs) = self._validate_configuration()
        self._run(self.config["control_host"], *api_args, **api_kwargs)

        self._post_run_actions(args)

        logger.info("END provision")

    @abstractmethod
    def _validate_configuration(
        self,
    ) -> Tuple[Tuple, Dict[str, Any]]:
        """Validate the job config and data and prepare the arguments
        for the Zapper `provision` API.
        """
        raise NotImplementedError

    def _run(self, zapper_ip, *args, **kwargs):
        """Run the Zapper `provision` API via RPyC. The arguments are
        not stricly defined so that the same API can be used by different
        implementations.

        The connector logger is passed as an argument to the Zapper API
        in order to get a real time feedback throughout the whole execution.
        """
        connection = rpyc.connect(
            zapper_ip,
            self.ZAPPER_SERVICE_PORT,
            config={
                "allow_public_attrs": True,
                "sync_request_timeout": self.ZAPPER_REQUEST_TIMEOUT,
            },
        )

        kwargs.update(
            {
                "agent_name": self.config["agent_name"],
                "cid": self.config.get("env", {}).get("CID"),
                "device_ip": self.config["device_ip"],
                "reboot_script": self.config["reboot_script"],
            }
        )

        connection.root.provision(
            self.PROVISION_METHOD,
            *args,
            logger=logger,
            **kwargs,
        )

    def _copy_ssh_id(self):
        """Copy the ssh id to the device."""
        logger.info("Copying the agent's SSH public key to the DUT.")

        try:
            test_username = self.job_data.get("test_data", {}).get(
                "test_username", "ubuntu"
            )
            test_password = self.job_data.get("test_data", {}).get(
                "test_password", "ubuntu"
            )
        except AttributeError:
            test_username = "ubuntu"
            test_password = "ubuntu"

        try:
            self.copy_ssh_key(
                self.config["device_ip"],
                test_username,
                test_password,
            )
        except RuntimeError as e:
            raise ProvisioningError(
                "Cannot copy the agent's SSH key to the DUT",
            ) from e

    @abstractmethod
    def _post_run_actions(self, args):
        """Run further actions after Zapper API returns successfully."""
