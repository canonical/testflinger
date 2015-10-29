# Copyright (C) 2015 Canonical
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

"""Raspberry Pi 2 support code."""

import logging
import multiprocessing
import subprocess
import yaml

import guacamole

import snappy_device_agents
from devices.rpi2.rpi2 import RaspberryPi2
from snappy_device_agents import logmsg


device_name = "rpi2"


class provision(guacamole.Command):

    """Tool for provisioning Raspberry Pi 2 with a given image."""

    def invoked(self, ctx):
        """Method called when the command is invoked."""
        with open(ctx.args.config) as configfile:
            config = yaml.load(configfile)
        snappy_device_agents.configure_logging(config)

        device = RaspberryPi2(ctx.args.config)
        logmsg(logging.INFO, "BEGIN provision")
        logmsg(logging.INFO, "Booting Master Image")
        device.ensure_master_image()
        image = snappy_device_agents.get_image(ctx.args.spi_data)
        server_ip = snappy_device_agents.get_local_ip_addr()
        q = multiprocessing.Queue()
        file_server = multiprocessing.Process(
            target=snappy_device_agents.serve_file, args=(q, image,))
        file_server.start()
        server_port = q.get()
        logmsg(logging.INFO, "Flashing Test Image")
        device.flash_sd(server_ip, server_port)
        file_server.terminate()
        logmsg(logging.INFO, "Booting Test Image")
        device.ensure_test_image()
        logmsg(logging.INFO, "END provision")

    def register_arguments(self, parser):
        """Method called to customize the argument parser."""
        parser.add_argument('-c', '--config', required=True,
                            help='Config file for this device')
        parser.add_argument('spi_data', help='SPI json data file')


class runtest(guacamole.Command):

    """Tool for running tests on a provisioned device."""

    def invoked(self, ctx):
        """Method called when the command is invoked."""
        with open(ctx.args.config) as configfile:
            config = yaml.load(configfile)
        snappy_device_agents.configure_logging(config)
        logmsg(logging.INFO, "BEGIN testrun")

        test_opportunity = snappy_device_agents.get_test_opportunity(
            ctx.args.spi_data)
        test_cmds = test_opportunity.get('test_payload').get('test_cmds')
        exitcode = 0
        for cmd in test_cmds:
            # Settings from the device yaml configfile like device_ip can be
            # formatted in test commands like "foo {device_ip}"
            try:
                cmd = cmd.format(**config)
            except:
                logmsg(logging.ERROR, "Unable to format command: %s", cmd)

            logmsg(logging.INFO, "Running: %s", cmd)
            proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT)
            rc = proc.wait()
            output, _ = proc.communicate()
            if rc:
                exitcode = 4
                logmsg(logging.WARNING, "Command failed, rc=%d", rc)
            logmsg(logging.INFO, "output:\n%s", output)
        logmsg(logging.INFO, "END testrun")
        return exitcode

    def register_arguments(self, parser):
        """Method called to customize the argument parser."""
        parser.add_argument('-c', '--config', required=True,
                            help='Config file for this device')
        parser.add_argument('spi_data', help='SPI json data file')


class DeviceAgent(guacamole.Command):

    """Device agent for Raspberry Pi 2."""

    sub_commands = (
        ('provision', provision),
        ('runtest', runtest),
    )
