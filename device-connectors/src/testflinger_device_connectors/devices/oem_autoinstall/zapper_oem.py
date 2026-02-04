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


import base64
import logging
from pathlib import Path
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
        supported_iso_types = {"bootstrap", "stock", "bios", "dummyefi"}
        provision_data = self.job_data["provision_data"]

        iso_type = provision_data.get("zapper_iso_type")
        meta_data_b64 = None
        user_data_b64 = None
        grub_cfg_b64 = None

        # Validate required fields
        if not self.config.get("device_ip"):
            raise ProvisioningError("device_ip is missing in config")

        dut_ip = self.config["device_ip"]

        if not provision_data.get("zapper_iso_url"):
            raise ProvisioningError(
                "zapper_iso_url is required in provision_data. "
                "Set ISO image to be flashed on typecmux USB."
            )

        if not provision_data.get("zapper_iso_type"):
            raise ProvisioningError(
                "zapper_iso_type is required in provision_data. "
                "Based on ISO type of zapper_iso_url argument."
            )

        if iso_type not in supported_iso_types:
            raise ProvisioningError(
                f"Unsupported ISO type: {iso_type}. "
                f"Supported types: {supported_iso_types}"
            )

        if iso_type == "stock":
            # Stock ISO requires meta-data, user-data and grub.cfg
            data_path = (
                Path(__file__).parent / "../../data/oem_autoinstall/stock"
            )
            meta_data_b64 = self._read_file_to_base64(
                data_path / "default-meta-data"
            )
            user_data_b64 = self._read_file_to_base64(
                data_path / "default-user-data"
            )
            grub_cfg_b64 = self._read_file_to_base64(
                data_path / "default-grub.cfg"
            )

        # Optional fields
        test_data = self.job_data.get("test_data", {})
        username = test_data.get("test_username", "ubuntu")
        password = test_data.get("test_password", "insecure")
        reboot_script = self.config.get("reboot_script")

        provisioning_data = {
            "zapper_iso_url": provision_data["zapper_iso_url"],
            "zapper_iso_type": iso_type,
            "user_template_update": provision_data.get(
                "user_template_update", False
            ),
            "device_ip": dut_ip,
            "username": username,
            "password": password,
            "reboot_script": reboot_script,
            "meta_data_b64": meta_data_b64,
            "user_data_b64": user_data_b64,
            "grub_cfg_b64": grub_cfg_b64,
        }

        return ((), provisioning_data)

    def _read_file_to_base64(self, filepath):
        """Read a file and return its base64 encoded content."""
        try:
            with open(filepath, "rb") as f:
                content = f.read()
                return base64.b64encode(content).decode("utf-8")
        except OSError as e:
            raise ProvisioningError(
                f"Failed to read file {filepath}: {e}"
            ) from e

    def _post_run_actions(self, args):
        pass
