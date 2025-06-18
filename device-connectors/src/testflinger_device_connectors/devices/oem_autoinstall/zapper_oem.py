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

from testflinger_device_connectors.devices import ProvisioningError
from testflinger_device_connectors.devices.zapper import ZapperConnector

logger = logging.getLogger(__name__)


class ZapperOem(ZapperConnector):
    PROVISION_METHOD = "ProvisioningOEM"

    def _validate_configuration(
        self,
    ) -> Tuple[Tuple, Dict[str, Any]]:
        """
        Validate the job config and data and prepare the arguments
        for the Zapper `provision` API.
        """
        logger.info("Validating configuration")
        supported_iso_types = {"bootstrap", "stock", "bios"}
        provision_data = self.job_data["provision_data"]
        iso_type = provision_data.get("zapper_iso_type")
        dut_ip = self.config["device_ip"]

        # Validate required fields
        if not provision_data.get("zapper_iso_url"):
            raise ProvisioningError(
                "zapper_iso_url is required in provision_data"
            )

        if iso_type not in supported_iso_types:
            raise ProvisioningError(
                f"Unsupported ISO type: {iso_type}. "
                f"Supported types: {supported_iso_types}"
            )

        if not self.config.get("device_ip"):
            raise ProvisioningError("device_ip is missing in config")

        # Optional fields
        test_data = self.job_data.get("test_data", {})
        username = test_data.get("test_username", "ubuntu")
        password = test_data.get("test_password", "insecure")
        reboot_script = self.config.get("reboot_script")

        provisioning_data = {
            "zapper_iso_url": provision_data["zapper_iso_url"],
            "zapper_iso_type": iso_type,
            "device_ip": dut_ip,
            "username": username,
            "password": password,
            "reboot_script": reboot_script,
        }

        return ((), provisioning_data)

    def _post_run_actions(self, args):
        pass
