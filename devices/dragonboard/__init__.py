# Copyright (C) 2016 Canonical
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

"""Dragonboard support code."""

import logging
import yaml

import guacamole

import snappy_device_agents
from devices.dragonboard.dragonboard import Dragonboard
from snappy_device_agents import logmsg
from devices import (Catch,
                     RecoveryError,
                     DefaultRuntest)

device_name = "dragonboard"


class provision(guacamole.Command):

    """Tool for provisioning baremetal with a given image."""

    @Catch(RecoveryError, 46)
    def invoked(self, ctx):
        """Method called when the command is invoked."""
        with open(ctx.args.config) as configfile:
            config = yaml.load(configfile)
        snappy_device_agents.configure_logging(config)
        device = Dragonboard(ctx.args.config, ctx.args.job_data)
        logmsg(logging.INFO, "BEGIN provision")
        logmsg(logging.INFO, "Booting Master Image")
        device.ensure_master_image()
        device.provision()

    def register_arguments(self, parser):
        """Method called to customize the argument parser."""
        parser.add_argument('-c', '--config', required=True,
                            help='Config file for this device')
        parser.add_argument('job_data', help='Testflinger json data file')


class DeviceAgent(guacamole.Command):

    """Device agent for Dragonboard."""

    sub_commands = (
        ('provision', provision),
        ('runtest', DefaultRuntest),
    )
