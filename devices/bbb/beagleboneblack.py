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

import subprocess
import time
import yaml


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
            print("DEBUG: running {}".format(cmd))
            try:
                subprocess.check_call(cmd.split(), timeout=10)
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
            print("DEBUG: running {}".format(cmd))
            try:
                subprocess.check_call(cmd.split(), timeout=20)
            except:
                raise RuntimeError("timeout reaching control host!")

    def ensure_test_image(self):
        """
        Actively switch the device to boot the test image.

        :raises RuntimeError:
            If the command times out or anything else fails.
        """
        # FIXME: I don't have a great way to ensure we're in the test image
        # yet, so just check that we're *not* in the emmc image
        print("DEBUG: Booting the test image")
        cmd = ['ssh', 'ubuntu@{}'.format(self.config['address']),
               'sudo /sbin/halt']
        try:
            subprocess.check_call(cmd)
        except:
            pass
        time.sleep(60)
        self.setboot('test')
        self.hardreset()

        emmc_booted = False
        started = time.time()
        while time.time() - started < 300:
            try:
                emmc_booted = self.is_emmc_image_booted()
            except:
                continue
            break
        # Check again if we are in the emmc image
        if emmc_booted:
            # XXX: This should *never* happen since we set the boot mode!
            raise RuntimeError("Still booting to emmc after flashing image!")

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
        cmd = ['ssh', 'ubuntu@{}'.format(self.config['address']),
               'cat /etc/issue']
        # FIXME: come up with a better way of checking this
        output = subprocess.check_output(
            cmd, stderr=subprocess.STDOUT, timeout=10)
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
        print("DEBUG: Making sure the emmc image is booted")
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

    def flash_sd(self, image_url):
        """
        Flash the image at :image_url to the sd card.

        :param image_url:
            URL of the image to flash. The image has to be compatible with a
            flat SD card layout. It will be downloaded and gunzipped over the
            SD card.
        :raises RuntimeError:
            If the command times out or anything else fails.
        """
        cmd = ['ssh', 'ubuntu@{}'.format(self.config['address']),
               'curl {} | gunzip| sudo dd of=/dev/mmcblk0 bs=32M'.format(
                   image_url)]
        print("DEBUG: running {}".format(cmd))
        try:
            # XXX: I hope 30 min is enough? but maybe not!
            subprocess.check_call(cmd, timeout=1800)
        except:
            raise RuntimeError("timeout reached while flashing image!")
