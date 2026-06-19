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

"""Control host connector for IoT provisioning.

The provisioning payload is built by the control host service; this connector
is a thin client that wraps the provisioning in serial logging and copies the
agent SSH key to the DUT when appropriate.
"""

import logging

from testflinger_device_connectors.devices import SerialLogger
from testflinger_device_connectors.devices.control_host import (
    ControlHostConnector,
)

logger = logging.getLogger(__name__)


class DeviceConnector(ControlHostConnector):
    """Tool for provisioning baremetal with a given image."""

    MANAGE_DUT_POWER_DURING_REBOOT = True
    PROVISION_METHOD = "iot"

    def provision(self, args):
        """Provision device with serial logging."""
        serial_host = self.config.get("serial_host")
        serial_port = self.config.get("serial_port")
        serial_proc = SerialLogger(
            serial_host, serial_port, "provision-serial.log"
        )
        serial_proc.start()
        try:
            super().provision(args)
        finally:
            serial_proc.stop()

    def _post_run_actions(self, args):
        """Run further actions after the control host returns successfully."""
        # When agent_ssh_access is false, the DUT won't be accessible
        # by the agent over SSH (its key is not authorized or no SSH
        # server is running at all), so don't attempt the key copy.
        # The key copy is also skipped when ubuntu_sso_email is set,
        # since the device is accessed with the SSO account keys instead.
        provision_data = self.job_data["provision_data"]

        agent_ssh_access = provision_data.get("agent_ssh_access", True)
        using_sso = bool(provision_data.get("ubuntu_sso_email"))

        if agent_ssh_access and not using_sso:
            self._copy_ssh_id()
