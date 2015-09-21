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
import subprocess
import time
import yaml

from devices import (ProvisioningError,
                     RecoveryError)


logger = logging.getLogger()


class RaspberryPi2:

    """Snappy Device Agent for Raspberry Pi 2."""

    def __init__(self, config):
        with open(config) as configfile:
            self.config = yaml.load(configfile)

    def setboot(self, mode):
        """
        Set the boot mode of the device.

        :param mode:
            One of 'master' or 'test'
        :raises RecoveryError:
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
                raise RecoveryError("timeout reaching control host!")

    def hardreset(self):
        """
        Reboot the device.

        :raises RecoveryError:
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
                raise RecoveryError("timeout reaching control host!")

    def ensure_test_image(self):
        """
        Actively switch the device to boot the test image.

        :raises ProvisioningError:
            If the command times out or anything else fails.
        """
        # FIXME: I don't have a great way to ensure we're in the test image
        # yet, so just check that we're *not* in the master image
        logger.info("Booting the test image")
        cmd = ['ssh', '-o', 'StrictHostKeyChecking=no',
               '-o', 'UserKnownHostsFile=/dev/null',
               'ubuntu@{}'.format(self.config['device_ip']),
               'sudo /sbin/halt']
        try:
            subprocess.check_call(cmd)
        except:
            pass
        time.sleep(60)
        self.setboot('test')
        self.hardreset()

        master_booted = False
        started = time.time()
        while time.time() - started < 300:
            try:
                master_booted = self.is_master_image_booted()
                if master_booted is False:
                    break
            except:
                continue
        # Check again if we are in the master image
        if master_booted:
            # XXX: This should *never* happen since we set the boot mode!
            raise ProvisioningError(
                "Still booting to master after flashing image!")

    def is_master_image_booted(self):
        """
        Check if the master image is booted.

        :returns:
            True if the master image is currently booted, False if another
            image is booted
        :raises CalledProcessError:
            If the command exits with an error
        :raises TimeoutExpired
            If the command times out

        .. note::
            The master contains the non-test image.
        """
        cmd = ['ssh', '-o', 'StrictHostKeyChecking=no',
               '-o', 'UserKnownHostsFile=/dev/null',
               'ubuntu@{}'.format(self.config['device_ip']),
               'apt-get -h']
        # apt-get -h under snappy returns a warning rather than full help
        output = subprocess.check_output(
            cmd, stderr=subprocess.STDOUT, timeout=60)
        if 'update' in str(output):
            return True
        else:
            return False

    def ensure_master_image(self):
        """
        Actively switch the device to boot the test image.

        :raises RecoveryError:
            If the command times out or anything else fails.
        """
        master_booted = False
        logger.info("Making sure the master image is booted")
        try:
            master_booted = self.is_master_image_booted()
        except:
            # don't worry if this doesn't work, we'll hard reset later
            pass

        if not master_booted:
            # We are not in the master image, so just hard reset
            self.setboot('master')
            self.hardreset()

            started = time.time()
            while time.time() - started < 300:
                try:
                    master_booted = self.is_master_image_booted()
                except:
                    continue
                break
            # Check again if we are in the master image
            if not master_booted:
                raise RecoveryError("Could not reboot to master!")

    def flash_sd(self, server_ip, server_port):
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
        cmd = ['ssh', '-o', 'StrictHostKeyChecking=no',
               '-o', 'UserKnownHostsFile=/dev/null',
               'ubuntu@{}'.format(self.config['device_ip']),
               'nc {} {}| gunzip| sudo dd of={} bs=16M'.format(
                   server_ip, server_port, self.config['test_device'])]
        logger.info("Running: %s", cmd)
        try:
            # XXX: I hope 30 min is enough? but maybe not!
            subprocess.check_call(cmd, timeout=1800)
        except:
            raise ProvisioningError("timeout reached while flashing image!")
