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
import logging
from typing import Any, Dict, Tuple
from testflinger_device_connectors.devices.zapper import ZapperConnector
from testflinger_device_connectors.devices import ProvisioningError
from testflinger_device_connectors.devices.zapper_iot.parser import (
    validate_provision_plan,
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

        provisioning_data = {
            "username": username,
            "password": password,
            "preset": self.job_data["provision_data"].get("preset"),
            "reboot_script": self.config["reboot_script"],
        }

        provision_plan = self.job_data["provision_data"].get("provision_plan")
        if provision_plan:

            try:
                validate_provision_plan(provision_plan)

                # Make sure the user created at provision time is
                # the same used during the test phase.
                provision_plan["config"]["username"] = username
                provision_plan["config"]["password"] = password

                provisioning_data["custom_provision_plan"] = provision_plan
            except ValueError as e:
                raise ProvisioningError from e

        urls = self.job_data["provision_data"].get("urls", [])
        try:
            validate_urls(urls)
        except ValueError as e:
            raise ProvisioningError from e
        provisioning_data["urls"] = urls

        return ((), provisioning_data)
