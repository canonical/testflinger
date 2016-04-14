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
import subprocess
import urllib.request
import time
import yaml

from devices import (ProvisioningError,
                     RecoveryError)

logger = logging.getLogger()


class Netboot:

    """Snappy Device Agent for Netboot."""

    def __init__(self, config):
        with open(config) as configfile:
            self.config = yaml.load(configfile)

    def setboot(self, mode):
        """
        Set the boot mode of the device.

        :param mode:
            One of 'master' or 'test'
        :raises ProvisioningError:
            If the command times out or anything else fails.

        This method sets the snappy boot method to the specified value.
        """
        if mode == 'master':
            setboot_script = self.config['select_master_script']
        elif mode == 'test':
            setboot_script = self.config['select_test_script']
        else:
            raise KeyError
        for cmd in setboot_script:
            logger.info("Running %s", cmd)
            try:
                subprocess.check_call(cmd.split(), timeout=60)
            except:
                raise ProvisioningError("timeout reaching control host!")

    def hardreset(self):
        """
        Reboot the device.

        :raises RecoveryError:
            If the command times out or anything else fails.

        .. note::
            This function runs the commands specified in 'reboot_script'
            in the config yaml.
        """
        for cmd in self.config['reboot_script']:
            logger.info("Running %s", cmd)
            try:
                subprocess.check_call(cmd.split(), timeout=60)
            except:
                raise RecoveryError("timeout reaching control host!")

    def ensure_test_image(self, test_username, test_password):
        """
        Actively switch the device to boot the test image.

        :param test_username:
            Username of the default user in the test image
        :param test_password:
            Password of the default user in the test image
        :raises ProvisioningError:
            If the command times out or anything else fails.
        """
        logger.info("Booting the test image")
        self.setboot('test')
        cmd = ['ssh', '-o', 'StrictHostKeyChecking=no',
               '-o', 'UserKnownHostsFile=/dev/null',
               'ubuntu@{}'.format(self.config['device_ip']),
               'sudo /sbin/reboot']
        try:
            subprocess.check_call(cmd)
        except:
            pass
        time.sleep(60)

        started = time.time()
        # Retry for a while since we might still be rebooting
        test_image_booted = False
        while time.time() - started < 300:
            try:
                time.sleep(10)
                cmd = ['sshpass', '-p', test_password, 'ssh-copy-id',
                       '-o', 'StrictHostKeyChecking=no',
                       '-o', 'UserKnownHostsFile=/dev/null',
                       '{}@{}'.format(test_username, self.config['device_ip'])]
                subprocess.check_call(cmd)
                test_image_booted = self.is_test_image_booted()
            except:
                pass
            if test_image_booted:
                break
        # Check again if we are in the master image
        if not test_image_booted:
            raise ProvisioningError("Failed to boot test image!")

    def is_test_image_booted(self):
        """
        Check if the master image is booted.

        :returns:
            True if the test image is currently booted, False otherwise.
        :raises TimeoutError:
            If the command times out
        :raises CalledProcessError:
            If the command fails
        """
        cmd = ['ssh', '-o', 'StrictHostKeyChecking=no',
               '-o', 'UserKnownHostsFile=/dev/null',
               'ubuntu@{}'.format(self.config['device_ip']),
               'snap -h']
        subprocess.check_output(
            cmd, stderr=subprocess.STDOUT, timeout=60)
        # If we get here, then the above command proved we are in snappy
        return True

    def is_master_image_booted(self):
        """
        Check if the master image is booted.

        :returns:
            True if the master image is currently booted, False otherwise.

        .. note::
            The master image is used for writing a new image to local media
        """
        check_url = 'http://{}:8989/check'.format(self.config['device_ip'])
        data = ""
        try:
            logger.info("Checking if master image booted: %s", check_url)
            with urllib.request.urlopen(check_url) as url:
                data = url.read()
        except:
            # Any connection error will fail through the normal path
            pass
        if 'Snappy Test Device Imager' in str(data):
            return True
        else:
            return False

    def ensure_master_image(self):
        """
        Actively switch the device to boot the test image.

        :raises RecoveryError:
            If the command times out or anything else fails.
        """
        logger.info("Making sure the master image is booted")
        master_booted = self.is_master_image_booted()

        if not master_booted:
            # We are not in the master image, so just hard reset
            self.setboot('master')
            self.hardreset()

            started = time.time()
            while time.time() - started < 300:
                time.sleep(10)
                master_booted = self.is_master_image_booted()
                if master_booted:
                    break
            # Check again if we are in the master image
            if not master_booted:
                raise RecoveryError("Could not reboot to master!")

    def flash_test_image(self, server_ip, server_port):
        """
        Flash the image at :image_url to the sd card.

        :param server_ip:
            IP address of the image server. The image will be downloaded and
            gunzipped over the SD card.
        :param server_port:
            TCP port to connect to on server_ip for downloading the image
        :raises ProvisioningError:
            If the command times out or anything else fails.
        """
        url = 'http://{}:8989/writeimage?server={}:{}\&dev={}'.format(
              self.config['device_ip'], server_ip, server_port,
              self.config['test_device'])
        logger.info("Triggering: %s", url)
        try:
            # XXX: I hope 30 min is enough? but maybe not!
            urllib.request.urlopen(url, timeout=1800)
        except:
            raise ProvisioningError("Error while flashing image!")

        # Now reboot the target system
        url = 'http://{}:8989/reboot'.format(self.config['device_ip'])
        try:
            logger.info("Rebooting target device: %s", url)
            urllib.request.urlopen(url, timeout=10)
        except:
            # FIXME: This could fail to return right now due to a bug
            pass
