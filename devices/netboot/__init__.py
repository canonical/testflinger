# Copyright (C) 2016-2019 Canonical
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

import snappy_device_agents
from devices.netboot.netboot import Netboot
from snappy_device_agents import logmsg

from devices import (Catch,
                     DefaultDevice,
                     ProvisioningError,
                     RecoveryError,
                     SerialLogger)

device_name = "netboot"


class DeviceAgent(DefaultDevice):

    """Tool for provisioning baremetal with a given image."""

    @Catch(RecoveryError, 46)
    def provision(self, args):
        """Method called when the command is invoked."""
        with open(args.config) as configfile:
            config = yaml.safe_load(configfile)
        snappy_device_agents.configure_logging(config)
        device = Netboot(args.config)
        image = snappy_device_agents.get_image(args.job_data)
        if not image:
            raise ProvisioningError('Error downloading image')
        server_ip = snappy_device_agents.get_local_ip_addr()
        # Ideally the default user/pass should be metadata about an image,
        # but we don't currently have any concept of that stored. For now,
        # we can give a reasonable guess based on the provisioning method.
        test_username = snappy_device_agents.get_test_username(
            job_data=args.job_data,
            default='admin')
        test_password = snappy_device_agents.get_test_password(
            job_data=args.job_data,
            default='admin')
        logmsg(logging.INFO, "BEGIN provision")
        logmsg(logging.INFO, "Booting Master Image")
        """Initial recovery process
        If the netboot (master) image is already booted and we can get to then
        URL for it, then just continue with provisioning. Otherwise, try to
        force it into the test image first, recopy the ssh keys if necessary,
        reboot if necessary, and get it into the netboot image before going on
        """
        if not device.is_master_image_booted():
            try:
                device.ensure_test_image(test_username, test_password)
                device.ensure_master_image()
            except ProvisioningError:
                raise RecoveryError("Unable to put system in a usable state!")
        q = multiprocessing.Queue()
        file_server = multiprocessing.Process(
            target=snappy_device_agents.serve_file, args=(q, image,))
        file_server.start()
        server_port = q.get()
        logmsg(logging.INFO, "Flashing Test Image")
        serial_host = config.get('serial_host')
        serial_port = config.get('serial_port')
        serial_proc = SerialLogger(
            serial_host, serial_port, 'provision-serial.log')
        serial_proc.start()
        try:
            device.flash_test_image(server_ip, server_port)
            logmsg(logging.INFO, "Booting Test Image")
            device.ensure_test_image(test_username, test_password)
        except Exception as e:
            raise e
        finally:
            file_server.terminate()
            serial_proc.stop()
        logmsg(logging.INFO, "END provision")
