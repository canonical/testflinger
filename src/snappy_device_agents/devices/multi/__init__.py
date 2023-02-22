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

"""Ubuntu multi-device support code."""

import json
import logging
import yaml

import snappy_device_agents
from snappy_device_agents import logmsg
from snappy_device_agents.devices import (
    DefaultDevice,
)
from snappy_device_agents.devices.multi.multi import Multi
from snappy_device_agents.devices.multi.tfclient import TFClient

device_name = "multi"


class DeviceAgent(DefaultDevice):

    """Device Agent for provisioning multiple devices at the same time"""

    def provision(self, args):
        """Method called when the command is invoked."""
        with open(args.config, encoding="utf-8") as configfile:
            config = yaml.safe_load(configfile)
        with open(args.job_data, encoding="utf-8") as jobfile:
            job_data = json.load(jobfile)
        snappy_device_agents.configure_logging(config)
        testflinger_server = config.get("testflinger_server")
        tfclient = TFClient(testflinger_server)
        device = Multi(config, job_data, tfclient)
        logmsg(logging.INFO, "BEGIN provision")
        logmsg(logging.INFO, "Provisioning device")
        device.provision()
        logmsg(logging.INFO, "END provision")
