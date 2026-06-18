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

"""Zapper Connector for IOT provisioning."""

import contextlib
import logging
from typing import Any, Dict, Tuple

from testflinger_device_connectors.devices import (
    ProvisioningError,
    SerialLogger,
)
from testflinger_device_connectors.devices.zapper import ZapperConnector
from testflinger_device_connectors.devices.zapper_iot.parser import (
    validate_urls,
)

logger = logging.getLogger(__name__)


class DeviceConnector(ZapperConnector):
    """Tool for provisioning baremetal with a given image."""

    MANAGE_DUT_POWER_DURING_REBOOT = True
    PROVISION_METHOD = "ProvisioningIoT"

    def _validate_configuration(
        self,
    ) -> Tuple[Tuple, Dict[str, Any]]:
        """Validate the job config and data and prepare the arguments
        for the Zapper `provision` API.
        """
        # We prefer using username/password in provision_plan
        # while username/password are not defined in test_data
        provision_plan = self.job_data.get("provision_data", {}).get(
            "provision_plan", {}
        )

        config = provision_plan.get("config", {})

        default_uname = config.get("username", "ubuntu")
        default_password = config.get("password", "ubuntu")

        username = self.job_data.get("test_data", {}).get(
            "test_username", default_uname
        )
        password = self.job_data.get("test_data", {}).get(
            "test_password", default_password
        )
        ubuntu_sso_email = self.job_data["provision_data"].get(
            "ubuntu_sso_email"
        )
        test_username = self.job_data.get("test_data", {}).get(
            "test_username", "ubuntu"
        )
        test_password = self.job_data.get("test_data", {}).get(
            "test_password", "ubuntu"
        )
        if username != test_username or password != test_password:
            logger.warning(
                "Provisioning is using a username different from"
                " what the test phase expects, which may prevent it"
                " from accessing the DUT later on."
            )

        # If ubuntu_sso_email is provided, use it instead of the test_username
        provisioning_data = {
            "username": username if not ubuntu_sso_email else ubuntu_sso_email,
            "password": password,
            "preset": self.job_data["provision_data"].get("preset"),
            "preset_kwargs": self.job_data["provision_data"].get(
                "preset_kwargs"
            ),
        }

        provision_plan = self.job_data["provision_data"].get("provision_plan")
        if provision_plan:
            try:
                # Ensure the provisioning username matches either the test
                # username or the Ubuntu SSO email if provided
                provision_plan["config"]["username"] = provisioning_data[
                    "username"
                ]
                provision_plan["config"]["password"] = provisioning_data[
                    "password"
                ]

                # For console-conf initial login, ubuntu_sso_email is required.
                # Validate that it was provided.
                run_stages = provision_plan["run_stage"]
                for stage in run_stages:
                    with contextlib.suppress(KeyError, TypeError):
                        if (
                            stage["initial_login"].get("method")
                            == "console-conf"
                        ):
                            if not ubuntu_sso_email:
                                raise ValueError(
                                    "ubuntu_sso_email is required "
                                    "when initial login using console-conf"
                                )
                            break

                provisioning_data["custom_provision_plan"] = provision_plan
            except (ValueError, KeyError) as e:
                raise ProvisioningError from e

        if url := self.job_data["provision_data"].get("url"):
            urls = [url]
        else:
            urls = self.job_data["provision_data"].get("urls", [])

        try:
            validate_urls(urls)
        except ValueError as e:
            raise ProvisioningError from e
        provisioning_data["urls"] = urls

        return ((), provisioning_data)

    def provision(self, args):
        """Provision device with serial logging."""
        serial_host = self.config.get("serial_host")
        serial_port = self.config.get("serial_port")
        serial_proc = SerialLogger(
            serial_host, serial_port, "provision-serial.log"
        )
        serial_proc.start()
        try:
            super().provision(args)
        finally:
            serial_proc.stop()

    def _post_run_actions(self, args):
        """Run further actions after Zapper API returns successfully."""
        super()._post_run_actions(args)

        # When agent_ssh_access is false, the DUT won't be accessible
        # by the agent over SSH (its key is not authorized or no SSH
        # server is running at all), so don't attempt the key copy.
        # The key copy is also skipped when ubuntu_sso_email is set,
        # since the device is accessed with the SSO account keys instead.
        provision_data = self.job_data["provision_data"]

        agent_ssh_access = provision_data.get("agent_ssh_access", True)
        using_sso = bool(provision_data.get("ubuntu_sso_email"))

        if agent_ssh_access and not using_sso:
            self._copy_ssh_id()
