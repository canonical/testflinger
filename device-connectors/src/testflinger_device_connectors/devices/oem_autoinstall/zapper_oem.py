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
from typing import Any, Dict, Optional, Tuple
from pathlib import Path
import yaml

from testflinger_device_connectors.devices import ProvisioningError
from testflinger_device_connectors.devices.zapper import ZapperConnector

logger = logging.getLogger(__name__)

class ZapperConnectorOem(ZapperConnector):
    """Tool for provisioning baremetal with a given image."""

    PROVISION_METHOD = "ProvisioningOEM"

    def _validate_configuration(
        self,
    ) -> Tuple[Tuple, Dict[str, Any]]:
        """
        Validate the job config and data and prepare the arguments
        for the Zapper `provision` API.
        """
        supported_iso_types = {"bootstrap", "stock", "bios"}
        iso_type = self.job_data["provision_data"]["zapper_iso_type"]
        if iso_type not in supported_iso_types:
            raise ValueError(
                f"Unsupported ISO type: {iso_type}. "
                f"Supported types: {supported_iso_types}"
            )

        provisioning_data = {
            "url_zapper_iso": self.job_data["provision_data"]["url_zapper_iso"],
            "iso_type": iso_type,
            "reboot_script": self.config["reboot_script"],
            "device_ip": self.config["device_ip"],
        }

        return ((), provisioning_data)

    def _post_run_actions():
        pass
        # Verify DUT online and ssh accessible?
        

