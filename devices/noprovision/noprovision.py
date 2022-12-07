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

"""Noprovision support code."""

import logging
import subprocess
import time
import yaml

from devices import ProvisioningError, RecoveryError

logger = logging.getLogger()


class Noprovision:

    """Snappy Device Agent for Noprovision."""

    def __init__(self, config):
        with open(config) as configfile:
            self.config = yaml.safe_load(configfile)

    def hardreset(self):
        """
        Reboot the device.

        :raises RecoveryError:
            If the command times out or anything else fails.

        .. note::
            This function runs the commands specified in 'reboot_script'
            in the config yaml.
        """
        for cmd in self.config["reboot_script"]:
            logger.info("Running %s", cmd)
            try:
                subprocess.check_call(cmd.split(), timeout=120)
            except subprocess.TimeoutExpired:
                raise RecoveryError("timeout reaching control host!")

    def ensure_test_image(self, test_username):
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
        cmd = [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "{}@{}".format(test_username, self.config["device_ip"]),
            "/bin/true",
        ]
        try:
            subprocess.check_call(cmd)
            return
        except subprocess.SubprocessError:
            pass

        self.hardreset()
        time.sleep(60)

        started = time.time()
        # Retry for a while since we might still be rebooting
        while time.time() - started < 300:
            try:
                time.sleep(10)
                cmd = [
                    "ssh",
                    "-o",
                    "StrictHostKeyChecking=no",
                    "-o",
                    "UserKnownHostsFile=/dev/null",
                    "{}@{}".format(test_username, self.config["device_ip"]),
                    "/bin/true",
                ]
                subprocess.check_call(cmd)
                return
            except subprocess.SubprocessError:
                # keep going if we aren't booted yet
                pass
        # If we got here, then it never booted to the test image
        raise ProvisioningError("Failed to boot test image!")
