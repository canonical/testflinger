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

"""Zapper Connector for KVM provisioning."""

import os
from typing import Any, Dict, Tuple

from testflinger_device_connectors.devices.zapper import ZapperConnector


class DeviceConnector(ZapperConnector):
    """Tool for provisioning baremetal with a given image."""

    PROVISION_METHOD = "zapper_kvm"

    def _get_autoinstall_conf(self, config, job_data):
        """Prepare autoinstall-related configuration."""
        autoinstall_conf = {}

        autoinstall_conf["storage_layout"] = job_data["provision_data"][
            "storage_layout"
        ]
        autoinstall_conf["storage_password"] = job_data["provision_data"].get(
            "storage_password"
        )

        if "base_user_data" in job_data["provision_data"]:
            autoinstall_conf["base_user_data"] = job_data["provision_data"][
                "base_user_data"
            ]

        with open(os.path.expanduser("~/.ssh/id_rsa.pub")) as pub:
            autoinstall_conf["authorized_keys"] = [pub.read()]

        return autoinstall_conf

    def _validate_configuration(
        self, config, job_data
    ) -> Tuple[Tuple[Any, ...], Dict[str, Any]]:
        """
        Validate the job config and data and prepare the arguments
        for the Zapper `provision` API.

        Strictly required arguments are:
        - url
        - device_ip
        - storage_layout
        - robot_tasks
        - reboot_script
        """
        provisioning_data = {}
        provisioning_data["url"] = job_data["provision_data"]["url"]
        provisioning_data["robot_tasks"] = job_data["provision_data"][
            "robot_tasks"
        ]
        provisioning_data["reboot_script"] = config["reboot_script"]
        provisioning_data["device_ip"] = config["device_ip"]
        provisioning_data["username"] = job_data.get("test_data", {}).get(
            "test_username", "ubuntu"
        )
        provisioning_data["password"] = job_data.get("test_password", {}).get(
            "test_password", "ubuntu"
        )

        provisioning_data["autoinstall_conf"] = self._get_autoinstall_conf(
            config, job_data
        )

        return ((), provisioning_data)
