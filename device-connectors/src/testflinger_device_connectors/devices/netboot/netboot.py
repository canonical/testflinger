# Copyright (C) 2023 Canonical
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
import time
import urllib.request

import yaml

from testflinger_device_connectors import CmdTimeoutError, runcmd
from testflinger_device_connectors.devices import (
    ProvisioningError,
    RecoveryError,
)

logger = logging.getLogger(__name__)


class Netboot:
    """Testflinger Device Connector for Netboot."""

    def __init__(self, config):
        with open(config) as configfile:
            self.config = yaml.safe_load(configfile)

    def setboot(self, mode):
        """Set the boot mode of the device.

        :param mode:
            One of 'master' or 'test'
        :raises ProvisioningError:
            If the command times out or anything else fails.

        This method sets the boot method to the specified value.
        """
        if mode == "master":
            setboot_script = self.config.get("select_master_script")
        elif mode == "test":
            setboot_script = self.config.get("select_test_script")
        else:
            raise ProvisioningError(
                "Attempted to set boot mode to '{}' - "
                "only 'master' or 'test' are supported "
                "modes!".format(mode)
            )
        self._run_cmd_list(setboot_script)

    def _run_cmd_list(self, cmdlist):
        """Run a list of commands.

        :param cmdlist:
            List of commands to run
        """
        if not cmdlist:
            return
        for cmd in cmdlist:
            logger.info("Running %s", cmd)
            try:
                rc = runcmd(cmd, timeout=60)
            except CmdTimeoutError as err:
                raise ProvisioningError(
                    "timeout reaching control host!"
                ) from err
            if rc:
                raise ProvisioningError(
                    "Error running {} (rc={})".format(cmd, rc)
                )

    def hardreset(self):
        """Reboot the device.

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
            except Exception as e:
                raise RecoveryError("timeout reaching control host!") from e

    def ensure_test_image(self, test_username, test_password):
        """Actively switch the device to boot the test image.

        :param test_username:
            Username of the default user in the test image
        :param test_password:
            Password of the default user in the test image
        :raises ProvisioningError:
            If the command times out or anything else fails.
        """
        logger.info("Booting the test image")
        if self.is_test_image_booted(test_username, test_password):
            return
        self.setboot("test")
        cmd = [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "{}@{}".format(test_username, self.config["device_ip"]),
            "sudo /sbin/reboot",
        ]
        try:
            subprocess.check_call(cmd, timeout=60)
        except Exception:
            self.hardreset()
        time.sleep(60)

        started = time.time()
        # Retry for a while since we might still be rebooting
        while time.time() - started < 900:
            time.sleep(10)
            if self.is_test_image_booted(test_username, test_password):
                return
        # If we got here, the test image never became available
        raise ProvisioningError("Failed to boot test image!")

    def is_test_image_booted(self, test_username, test_password):
        """Check if the test image is booted.

        :returns:
            True if the test image is currently booted, False otherwise.
        :param test_username:
            Username of the default user in the test image
        :param test_password:
            Password of the default user in the test image
        :returns:
            True if the test image is currently booted, False otherwise.
        """
        cmd = [
            "sshpass",
            "-p",
            test_password,
            "ssh-copy-id",
            "-f",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "{}@{}".format(test_username, self.config["device_ip"]),
        ]
        try:
            subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=60)
        except Exception:
            return False
        # If we get here, the above command proved we are in the test image
        return True

    def is_master_image_booted(self):
        """Check if the master image is booted.

        :returns:
            True if the master image is currently booted, False otherwise.

        .. note::
            The master image is used for writing a new image to local media
        """
        check_url = "http://{}:8989/check".format(self.config["device_ip"])
        data = ""
        try:
            logger.info("Checking if master image booted: %s", check_url)
            with urllib.request.urlopen(check_url) as url:
                data = url.read()
        except Exception:
            # Any connection error will fail through the normal path
            pass
        if "Snappy Test Device Imager" in str(data):
            return True
        else:
            return False

    def ensure_master_image(self):
        """Actively switch the device to boot the test image.

        :raises RecoveryError:
            If the command times out or anything else fails.
        """
        logger.info("Making sure the master image is booted")
        if self.is_master_image_booted():
            return

        self.setboot("master")
        self.hardreset()

        started = time.time()
        while time.time() - started < 600:
            time.sleep(10)
            master_is_booted = self.is_master_image_booted()
            if master_is_booted:
                break
        # Check again if we are in the master image
        if not master_is_booted:
            raise RecoveryError("Could not reboot to master image!")

    def flash_test_image(self, server_ip, server_port):
        """Flash the image at :image_url to the sd card.

        :param server_ip:
            IP address of the image server. The image will be downloaded and
            uncompressed over the SD card.
        :param server_port:
            TCP port to connect to on server_ip for downloading the image
        :raises ProvisioningError:
            If the command times out or anything else fails.
        """
        url = r"http://{}:8989/writeimage?server={}:{}\&dev={}".format(
            self.config["device_ip"],
            server_ip,
            server_port,
            self.config["test_device"],
        )
        logger.info("Triggering: %s", url)
        try:
            # XXX: I hope 30 min is enough? but maybe not!
            req = urllib.request.urlopen(url, timeout=1800)
            logger.info("Image write output:")
            logger.info(str(req.read()))
        except Exception as e:
            raise ProvisioningError("Error while flashing image!") from e

        # Run post-flash hooks
        post_flash_cmds = self.config.get("post_flash_cmds")
        self._run_cmd_list(post_flash_cmds)

        # Now reboot the target system
        url = "http://{}:8989/reboot".format(self.config["device_ip"])
        try:
            logger.info("Rebooting target device: %s", url)
            urllib.request.urlopen(url, timeout=10)
        except Exception:
            # FIXME: This could fail to return right now due to a bug
            pass
