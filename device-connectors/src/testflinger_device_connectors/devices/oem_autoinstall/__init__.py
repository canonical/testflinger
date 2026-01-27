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

"""Device connector to provision Ubuntu OEM on systems
that support autoinstall and provision-image.sh script.
"""

import json
import logging
from pathlib import Path

import yaml

from testflinger_device_connectors.devices import (
    DefaultDevice,
    ProvisioningError,
)
from testflinger_device_connectors.devices.oem_autoinstall.oem_autoinstall import (  # noqa: E501
    OemAutoinstall,
)
from testflinger_device_connectors.devices.oem_autoinstall.zapper_oem import (
    ZapperOem,
)
from testflinger_device_connectors.devices.zapper import ZapperConnector

logger = logging.getLogger(__name__)


class DeviceConnector(DefaultDevice):
    """Tool for provisioning baremetal with a given image."""

    def provision(self, args):
        """Provision device when the command is invoked."""
        super().provision(args)

        with open(args.job_data, encoding="utf-8") as job_json:
            self.job_data = json.load(job_json)
        provision_data = self.job_data.get("provision_data", {})
        config = self._load_config(args.config)

        uses_zapper_iso = provision_data.get(
            "zapper_iso_type"
        ) and provision_data.get("zapper_iso_url")

        self._disconnect_usb_stick(config, blocking=uses_zapper_iso)

        if provision_data.get("zapper_iso_type") or provision_data.get(
            "zapper_iso_url"
        ):
            logger.info("Init zapper_oem on agent")
            device_with_zapper = ZapperOem(config)
            device_with_zapper.provision(args)
            logger.info("Return to oem_autoinstall")

        if provision_data.get("url"):
            logger.info("BEGIN provision via oem_autoinstall")
            device = OemAutoinstall(args.config, args.job_data)
            logger.info("Provisioning device")
            device.provision()
            logger.info("END provision via oem_autoinstall")

    def _disconnect_usb_stick(self, config: dict, blocking: bool) -> None:
        """Try to disconnect the USB stick via typecmux if a Zapper is available.

        :param config: The device configuration.
        :param blocking: If True, raise an error if Zapper is not available.
        """
        control_host = config.get("control_host")
        if not control_host:
            if blocking:
                raise ProvisioningError(
                    "control_host is required when using zapper_iso_type "
                    "and zapper_iso_url"
                )
            return

        try:
            self.wait_online(
                ZapperConnector.check_rpyc_server_on_host,
                control_host,
                60,
            )
            ZapperConnector.typecmux_set_state(control_host, "OFF")
        except (TimeoutError, ConnectionError, Exception) as e:
            if blocking:
                raise ProvisioningError(
                    f"Cannot reach the Zapper service over RPyC on "
                    f"{control_host}: {e}"
                ) from e
            logger.debug(
                "Could not disconnect USB stick on %s: %s", control_host, e
            )

    def _load_config(self, config_path):
        """Load YAML config file and return as dict."""
        with open(Path(config_path)) as f:
            return yaml.safe_load(f) or {}
