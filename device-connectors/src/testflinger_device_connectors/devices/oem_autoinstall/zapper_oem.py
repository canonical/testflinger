# Copyright (C) 2025 Canonical
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


import logging
from typing import Any, Dict, Tuple
import json

from testflinger_device_connectors.devices import ProvisioningError
from testflinger_device_connectors.devices.zapper import ZapperConnector

logger = logging.getLogger(__name__)

class ZapperOem(ZapperConnector):
    """Tool for provisioning baremetal with a given image."""

    PROVISION_METHOD = "ProvisioningOEM"

    def _validate_configuration(
        self,
    ) -> Tuple[Tuple, Dict[str, Any]]:
        """
        Validate the job config and data and prepare the arguments
        for the Zapper `provision` API.
        """
        logger.info("zapper_oem: Validating configuration")
        supported_iso_types = {"bootstrap", "stock", "bios"}
        iso_type = self.job_data["provision_data"].get("zapper_iso_type")

        if iso_type not in supported_iso_types:
            error_msg = (
                f"Unsupported ISO type: {iso_type}. "
                f"Supported types: {supported_iso_types}"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        provisioning_data = {
            "zapper_iso_url": self.job_data["provision_data"].get("zapper_iso_url"),
            "zapper_iso_type": iso_type,
            "device_ip": self.config["device_ip"],
        }

        # Add reboot_script if it exists in config
        if "reboot_script" in self.config:
            provisioning_data["reboot_script"] = self.config["reboot_script"]

        logger.info("Validated zapper provisioning data: %s", json.dumps(provisioning_data, indent=2))
        return ((), provisioning_data)

    def _post_run_actions(self, args):
        logger.info("oem_autoinstall/zapper_oem.py: Skip _post_run_actions")

