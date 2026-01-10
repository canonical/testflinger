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

"""
Ubuntu Core Re-Install Provisioning
For machines running Ubuntu Core, it is possible to get to a clean system
using the same image by calling the "command snap reboot --install"
"""

import logging
import subprocess
from testflinger_device_connectors.devices.oemrecovery.oemrecovery import (
    OemRecovery,
)

logger = logging.getLogger(__name__)


class UbuntuCoreReinstall(OemRecovery):
    """Device Agent for Ubuntu Core machines"""

    def provision(self):
        """Provision the device"""

        # First, ensure the device is online and reachable
        try:
            self.copy_ssh_id()
        except subprocess.CalledProcessError:
            self.hardreset()
            self.check_device_booted()

        logger.info("Running Ubuntu Core Re-install")
        recovery_cmds = ["sudo snap reboot --install"]
        self._run_cmd_list(recovery_cmds)
        self.check_device_booted()
