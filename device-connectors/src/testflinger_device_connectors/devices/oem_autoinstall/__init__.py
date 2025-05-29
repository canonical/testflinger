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

import logging

from testflinger_device_connectors.devices import (
    DefaultDevice,
)
from testflinger_device_connectors.devices.oem_autoinstall.oem_autoinstall import (  # noqa: E501
    OemAutoinstall,
)
from testflinger_device_connectors.devices.oem_autoinstall.zapper_oem import (
    ZapperConnectorOem,
)

logger = logging.getLogger(__name__)


class DeviceConnector(DefaultDevice):
    """Tool for provisioning baremetal with a given image."""

    def provision(self, args):
        """Provision device when the command is invoked."""
        with open(args.job_data, encoding="utf-8") as job_json:
            self.job_data = json.load(job_json)
        provision_data = self.job_data.get("provision_data", {})

        if provision_data.get("zapper_usb_url"):
            logger.info("Using Zapper USB")
            device_with_zapper = ZapperConnectorOem()
            logger.info("BEGIN provision via Zapper")
            logger.info("Provisioning device via Zapper")
            device_with_zapper.provision()
            logger.info("END provision via Zapper")

        if provision_data.get("url"):
            device = OemAutoinstall(args.config, args.job_data)
            logger.info("BEGIN provision")
            logger.info("Provisioning device")
            device.provision()
            logger.info("END provision")
