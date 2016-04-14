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
import subprocess
import time
import yaml

from devices import ProvisioningError

logger = logging.getLogger()


class BeagleBoneBlack:

    """Snappy Device Agent for Beagle Bone Black."""

    def __init__(self, config):
        with open(config) as configfile:
            self.config = yaml.load(configfile)

    def setboot(self, mode):
        """
        Set the boot mode of the device.

        :param mode:
            One of 'master' or 'test'
        :raises RuntimeError:
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
                raise RuntimeError("timeout reaching control host!")

    def hardreset(self):
        """
        Reboot the device.

        :raises RuntimeError:
            If the command times out or anything else fails.

        .. note::
            This function executes ``bin/hardreset`` which is not a part of a
            standard image. You need to provide it yourself.
        """
        for cmd in self.config['reboot_script']:
            logger.info("running %s", cmd)
            try:
                subprocess.check_call(cmd.split(), timeout=60)
            except:
                raise RuntimeError("timeout reaching control host!")

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
               'sudo /sbin/halt']
        try:
            subprocess.check_call(cmd)
        except:
            pass
        time.sleep(60)
        self.hardreset()

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

    def is_emmc_image_booted(self):
        """
        Check if the emmc image is booted.

        :returns:
            True if the emmc image is currently booted, False otherwise.
        :raises RuntimeError:
            If the command times out or anything else fails.

        .. note::
            The emmc contains the non-test image.
        """
        cmd = ['ssh', '-o', 'StrictHostKeyChecking=no',
               '-o', 'UserKnownHostsFile=/dev/null',
               'ubuntu@{}'.format(self.config['device_ip']),
               'cat /etc/issue']
        # FIXME: come up with a better way of checking this
        output = subprocess.check_output(
            cmd, stderr=subprocess.STDOUT, timeout=60)
        if 'BeagleBoardUbuntu' in str(output):
            return True
        return False

    def ensure_emmc_image(self):
        """
        Actively switch the device to boot the test image.

        :raises RuntimeError:
            If the command times out or anything else fails.
        """
        emmc_booted = False
        logger.info("Making sure the emmc image is booted")
        try:
            emmc_booted = self.is_emmc_image_booted()
        except:
            # don't worry if this doesn't work, we'll hard reset later
            pass

        if not emmc_booted:
            # We are not in the emmc image, so just hard reset
            self.setboot('master')
            self.hardreset()

            started = time.time()
            while time.time() - started < 300:
                try:
                    emmc_booted = self.is_emmc_image_booted()
                except:
                    continue
                break
            # Check again if we are in the emmc image
            if not emmc_booted:
                raise RuntimeError("Could not reboot to emmc!")

    def flash_sd(self, server_ip, server_port):
        """
        Flash the image at :image_url to the sd card.

        :param server_ip:
            IP address of the image server. The image will be downloaded and
            gunzipped over the SD card.
        :param server_port:
            TCP port to connect to on server_ip for downloading the image
        :raises RuntimeError:
            If the command times out or anything else fails.
        """
        cmd = ['ssh', '-o', 'StrictHostKeyChecking=no',
               '-o', 'UserKnownHostsFile=/dev/null',
               'ubuntu@{}'.format(self.config['device_ip']),
               'nc {} {}| gunzip| sudo dd of=/dev/mmcblk0 bs=16M'.format(
                   server_ip, server_port)]
        logger.info("Running: %s", cmd)
        try:
            # XXX: I hope 30 min is enough? but maybe not!
            subprocess.check_call(cmd, timeout=1800)
        except:
            raise RuntimeError("timeout reached while flashing image!")
