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

from testflinger_device_connectors.devices import ProvisioningError
from testflinger_device_connectors.devices.zapper import ZapperConnector
from testflinger_device_connectors.devices.zapper_iot.parser import (
    validate_urls,
)

logger = logging.getLogger(__name__)


class DeviceConnector(ZapperConnector):
    """Tool for provisioning baremetal with a given image."""

    PROVISION_METHOD = "ProvisioningIoT"

    def _validate_configuration(
        self,
    ) -> Tuple[Tuple, Dict[str, Any]]:
        """
        Validate the job config and data and prepare the arguments
        for the Zapper `provision` API.
        """

        username = self.job_data.get("test_data", {}).get(
            "test_username", "ubuntu"
        )
        password = self.job_data.get("test_data", {}).get(
            "test_password", "ubuntu"
        )
        ubuntu_sso_email = self.job_data["provision_data"].get(
            "ubuntu_sso_email"
        )

        # If ubuntu_sso_email is provided, use it instead of the test_username
        provisioning_data = {
            "username": username if not ubuntu_sso_email else ubuntu_sso_email,
            "password": password,
            "preset": self.job_data["provision_data"].get("preset"),
            "reboot_script": self.config["reboot_script"],
            "device_ip": self.config["device_ip"],
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

        urls = self.job_data["provision_data"].get("urls", [])
        try:
            validate_urls(urls)
        except ValueError as e:
            raise ProvisioningError from e
        provisioning_data["urls"] = urls

        return ((), provisioning_data)

    def _post_run_actions(self, args):
        """Run further actions after Zapper API returns successfully."""
        super()._post_run_actions(args)

        # Copy the ssh id if ubuntu_sso_email is not provided in provision_data
        if not self.job_data["provision_data"].get("ubuntu_sso_email"):
            self._copy_ssh_id()
