# Copyright (C) 2017-2023 Canonical
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

"""Ubuntu MAAS 2.x CLI support code."""

import logging

import yaml

from testflinger_device_connectors.devices import (
    DefaultDevice,
    ProvisioningError,
    SerialLogger,
)
from testflinger_device_connectors.devices.maas2.maas2 import Maas2

logger = logging.getLogger(__name__)


class DeviceConnector(DefaultDevice):
    """Tool for provisioning baremetal with a given image."""

    def provision(self, args):
        """Method called when the command is invoked."""
        with open(args.config) as configfile:
            config = yaml.safe_load(configfile)
        device = Maas2(args.config, args.job_data)
        logger.info("BEGIN provision")
        logger.info("Provisioning device")
        serial_host = config.get("serial_host")
        serial_port = config.get("serial_port")
        serial_proc = SerialLogger(
            serial_host, serial_port, "provision-serial.log"
        )
        serial_proc.start()
        try:
            device.provision()
        except ProvisioningError as err:
            logger.error("Provisioning failed: %s", str(err))
            raise
        finally:
            serial_proc.stop()
            logger.info("END provision")

    def cleanup(self, args):
        device = Maas2(args.config, args.job_data)
        try:
            device.cleanup()
        except ProvisioningError as err:
            logger.error("Provisioning failed: %s", str(err))
            raise
