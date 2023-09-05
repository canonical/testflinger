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

"""
Ubuntu OEM Recovery Provisioning for Lenovo OEM devices
Use this for systems that can use the oem recovery-from-iso.sh script
for provisioning, but require the --ubr flag in order to use the
"ubuntu recovery" method.
"""

import logging

import yaml

import snappy_device_agents
from snappy_device_agents import logmsg
from snappy_device_agents.devices import DefaultDevice, RecoveryError, catch
from .lenovo_oemscript import LenovoOemScript

device_name = "lenovo_oemscript"


class DeviceAgent(DefaultDevice):

    """Tool for provisioning Lenovo OEM devices with an oem image."""

    @catch(RecoveryError, 46)
    def provision(self, args):
        """Method called when the command is invoked."""
        with open(args.config) as configfile:
            config = yaml.safe_load(configfile)
        snappy_device_agents.configure_logging(config)
        device = LenovoOemScript(args.config, args.job_data)
        logmsg(logging.INFO, "BEGIN provision")
        logmsg(logging.INFO, "Provisioning device")
        device.provision()
        logmsg(logging.INFO, "END provision")
