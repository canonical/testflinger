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

"""Netboot support code."""

import logging
import multiprocessing
import yaml

import guacamole

import snappy_device_agents
from devices.netboot.netboot import Netboot
from snappy_device_agents import logmsg, run_test_cmds

from devices import (Catch, RecoveryError)

device_name = "netboot"


class provision(guacamole.Command):

    """Tool for provisioning baremetal with a given image."""

    @Catch(RecoveryError, 46)
    def invoked(self, ctx):
        """Method called when the command is invoked."""
        with open(ctx.args.config) as configfile:
            config = yaml.load(configfile)
        snappy_device_agents.configure_logging(config)
        device = Netboot(ctx.args.config)
        logmsg(logging.INFO, "BEGIN provision")
        logmsg(logging.INFO, "Booting Master Image")
        device.ensure_master_image()
        image = snappy_device_agents.get_image(ctx.args.job_data)
        server_ip = snappy_device_agents.get_local_ip_addr()
        test_username = snappy_device_agents.get_test_username(
            ctx.args.job_data)
        test_password = snappy_device_agents.get_test_password(
            ctx.args.job_data)
        q = multiprocessing.Queue()
        file_server = multiprocessing.Process(
            target=snappy_device_agents.serve_file, args=(q, image,))
        file_server.start()
        server_port = q.get()
        logmsg(logging.INFO, "Flashing Test Image")
        device.flash_test_image(server_ip, server_port)
        file_server.terminate()
        logmsg(logging.INFO, "Booting Test Image")
        device.ensure_test_image(test_username, test_password)
        logmsg(logging.INFO, "END provision")

    def register_arguments(self, parser):
        """Method called to customize the argument parser."""
        parser.add_argument('-c', '--config', required=True,
                            help='Config file for this device')
        parser.add_argument('job_data', help='Testflinger json data file')


class runtest(guacamole.Command):

    """Tool for running tests on a provisioned device."""

    def invoked(self, ctx):
        """Method called when the command is invoked."""
        with open(ctx.args.config) as configfile:
            config = yaml.load(configfile)
        snappy_device_agents.configure_logging(config)
        logmsg(logging.INFO, "BEGIN testrun")

        test_opportunity = snappy_device_agents.get_test_opportunity(
            ctx.args.job_data)
        test_cmds = test_opportunity.get('test_data').get('test_cmds')
        exitcode = run_test_cmds(test_cmds, config)
        logmsg(logging.INFO, "END testrun")
        return exitcode

    def register_arguments(self, parser):
        """Method called to customize the argument parser."""
        parser.add_argument('-c', '--config', required=True,
                            help='Config file for this device')
        parser.add_argument('job_data', help='Testflinger json data file')


class DeviceAgent(guacamole.Command):

    """Device agent for Netboot."""

    sub_commands = (
        ('provision', provision),
        ('runtest', runtest),
    )
