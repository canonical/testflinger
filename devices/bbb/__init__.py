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

"""Beagle Bone Black support code."""

import logging
import multiprocessing
import subprocess
import yaml

import guacamole

import snappy_device_agents
from devices.bbb.beagleboneblack import BeagleBoneBlack

device_name = "bbb"

logger = logging.getLogger()


class provision(guacamole.Command):

    """Tool for provisioning beagle bone black with a given image."""

    def invoked(self, ctx):
        """Method called when the command is invoked."""
        with open(ctx.args.config) as configfile:
            config = yaml.load(configfile)
        snappy_device_agents.configure_logging(config)

        device = BeagleBoneBlack(ctx.args.config)
        logger.info("BEGIN provision")
        logger.info("Booting Master Image")
        device.ensure_emmc_image()
        image = snappy_device_agents.get_image(ctx.args.spi_data)
        server_ip = snappy_device_agents.get_local_ip_addr()
        q = multiprocessing.Queue()
        file_server = multiprocessing.Process(
            target=snappy_device_agents.serve_file, args=(q, image,))
        file_server.start()
        server_port = q.get()
        logger.info("Flashing Test Image")
        device.flash_sd(server_ip, server_port)
        file_server.terminate()
        logger.info("Booting Test Image")
        device.ensure_test_image()
        logger.info("END provision")

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
        logger.info("BEGIN testrun")

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
                exitcode = 20
                logger.error("Unable to format command: %s", cmd)

            logger.info("Running: %s", cmd)
            proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT)
            rc = proc.wait()
            output, _ = proc.communicate()
            if rc:
                exitcode = 4
                logger.warn("Command failed, rc=%d", rc)
            logger.info("output:\n%s", output)
        logger.info("END testrun")
        return exitcode

    def register_arguments(self, parser):
        """Method called to customize the argument parser."""
        parser.add_argument('-c', '--config', required=True,
                            help='Config file for this device')
        parser.add_argument('spi_data', help='SPI json data file')


class DeviceAgent(guacamole.Command):

    """Device agent for BeagleBone Black."""

    sub_commands = (
        ('provision', provision),
        ('runtest', runtest),
    )
