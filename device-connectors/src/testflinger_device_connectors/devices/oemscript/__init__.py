# Copyright (C) 2023 Canonical
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

"""Ubuntu OEM Recovery provisioner support code."""

import logging

import yaml

from testflinger_device_connectors.devices import (
    DefaultDevice,
)
from testflinger_device_connectors.devices.oemscript.oemscript import OemScript
from testflinger_device_connectors.devices.zapper import ZapperConnector

logger = logging.getLogger(__name__)


class DeviceConnector(DefaultDevice):
    """Tool for provisioning baremetal with a given image."""

    def provision(self, args):
        """Provision device when the command is invoked."""
        super().provision(args)

        with open(args.config) as configfile:
            config = yaml.safe_load(configfile)

        self._disconnect_usb_stick(config)

        device = OemScript(args.config, args.job_data)
        logger.info("BEGIN provision")
        logger.info("Provisioning device")
        device.provision()
        logger.info("END provision")

    def _disconnect_usb_stick(self, config: dict) -> None:
        """Try to disconnect the USB stick via typecmux if a Zapper is available.

        This is a non-blocking operation - if the Zapper is not available,
        we simply skip this step.
        """
        control_host = config.get("control_host")
        if not control_host:
            return

        try:
            self.wait_online(
                ZapperConnector.check_rpyc_server_on_host,
                control_host,
                60,
            )
            ZapperConnector.typecmux_set_state(control_host, "OFF")
        except (TimeoutError, ConnectionError, Exception) as e:
            logger.debug(
                "Could not disconnect USB stick on %s: %s", control_host, e
            )
