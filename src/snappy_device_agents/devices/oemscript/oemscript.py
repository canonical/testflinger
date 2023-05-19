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

"""Ubuntu OEM Script Provisioner support code."""

import json
import logging
import os
from pathlib import Path
import subprocess
import time
import yaml

from snappy_device_agents import download
from snappy_device_agents.devices import ProvisioningError, RecoveryError

logger = logging.getLogger()


class OemScript:

    """Device Agent for OEM Script."""

    def __init__(self, config, job_data):
        with open(config, encoding="utf-8") as configfile:
            self.config = yaml.safe_load(configfile)
        with open(job_data, encoding="utf-8") as job_json:
            self.job_data = json.load(job_json)

    def run_on_control_host(self, cmd, timeout=60):
        """
        Run a command on the control host over ssh

        :param cmd:
            Command to run
        :param timeout:
            Timeout (default 60)
        :returns:
            returncode, stdout
        """
        try:
            test_username = self.job_data.get("test_data", {}).get(
                "test_username", "ubuntu"
            )
        except AttributeError:
            test_username = "ubuntu"
        ssh_cmd = [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            f"{test_username}@{self.config['device_ip']}",
            cmd,
        ]
        proc = subprocess.run(
            ssh_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, proc.stdout

    def provision(self):
        """Provision the device"""

        # First, ensure the device is online and reachable
        try:
            self.copy_ssh_id()
        except subprocess.CalledProcessError:
            self.hardreset()
            self.check_device_booted()

        provision_data = self.job_data.get("provision_data", {})
        image_url = provision_data.get("url")

        # Download the .iso image from image_url
        if not image_url:
            logger.error(
                "Please provide an image 'url' in the provision_data section"
            )
            raise ProvisioningError("No image url provided")
        image_file = download(image_url)

        self.run_recovery_script(image_file)

        self.check_device_booted()

    def run_recovery_script(self, image_file):
        """Download and run the OEM recovery script"""
        device_ip = self.config["device_ip"]

        data_path = Path(__file__).parent / "../../data/muxpi/oemscript"
        recovery_script = data_path / "recovery-from-iso.sh"

        # Run the recovery script
        logger.info("Running recovery script")
        cmd = [
            recovery_script,
            "--local-iso",
            image_file,
            "--inject-ssh-key",
            os.path.expanduser("~/.ssh/id_rsa.pub"),
            "-t",
            device_ip,
        ]
        proc = subprocess.run(
            cmd,
            timeout=60 * 60,  # 1 hour - just in case
            check=False,
        )
        if proc.returncode:
            logger.error(
                "Recovery script failed with return code %s", proc.returncode
            )
            raise ProvisioningError("Recovery script failed")

    def copy_ssh_id(self):
        """Copy the ssh id to the device"""
        try:
            test_username = self.job_data.get("test_data", {}).get(
                "test_username", "ubuntu"
            )
            test_password = self.job_data.get("test_data", {}).get(
                "test_password", "ubuntu"
            )
        except AttributeError:
            test_username = "ubuntu"
            test_password = "ubuntu"
        cmd = [
            "sshpass",
            "-p",
            test_password,
            "ssh-copy-id",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            f"{test_username}@{self.config['device_ip']}",
        ]
        subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=60)

    def check_device_booted(self):
        """Check to see if the device is booted and reachable with ssh"""
        logger.info("Checking to see if the device is available.")
        started = time.time()
        # Wait for provisioning to complete - can take a very long time
        while time.time() - started < 3600:
            try:
                time.sleep(90)
                self.copy_ssh_id()
                return True
            except subprocess.SubprocessError:
                pass
        # If we get here, then we didn't boot in time
        agent_name = self.config.get("agent_name")
        logger.error(
            "Device %s unreachable,  provisioning" "failed!", agent_name
        )
        raise ProvisioningError("Failed to boot test image!")

    def _run_cmd_list(self, cmdlist):
        """
        Run a list of commands

        :param cmdlist:
            List of commands to run
        """
        if not cmdlist:
            return
        for cmd in cmdlist:
            logger.info("Running %s", cmd)
            try:
                return_code, output = self.run_on_control_host(
                    cmd, timeout=600
                )
            except subprocess.TimeoutExpired as exc:
                raise ProvisioningError(
                    "timeout reaching control host!"
                ) from exc
            if return_code:
                raise ProvisioningError(output)
            logger.info(output)

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
            except subprocess.SubprocessError as exc:
                raise RecoveryError("Error running reboot script!") from exc
