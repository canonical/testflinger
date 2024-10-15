# Copyright (C) 2024 Canonical
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

"""
Starting from Ubuntu 24.04, OEM uses autoinstall to provision
the PC platforms for all vendors.
Use this device connector for systems that support autoinstall provisioning
with provision-image.sh script
"""

import json
import logging
from pathlib import Path
import subprocess
import yaml
import shutil
import time

from testflinger_device_connectors.devices import (
    ProvisioningError,
    RecoveryError,
)

logger = logging.getLogger(__name__)
ATTACHMENTS_DIR = "attachments"
ATTACHMENTS_PROV_DIR = Path.cwd() / ATTACHMENTS_DIR / "provision"


class OemAutoinstall:
    """Device Connector for OEM Script."""

    def __init__(self, config, job_data):
        with open(config, encoding="utf-8") as configfile:
            self.config = yaml.safe_load(configfile)
        with open(job_data, encoding="utf-8") as job_json:
            self.job_data = json.load(job_json)
        self.data_path = Path(__file__).parent / "../../data/oem_autoinstall"

    def provision(self):
        """Provision the device"""

        # Ensure the device is online and reachable
        try:
            self.copy_ssh_id()
        except subprocess.CalledProcessError:
            self.hardreset()
            self.check_device_booted()

        provision_data = self.job_data.get("provision_data", {})
        image_url = provision_data.get("url")
        token_file = provision_data.get("token_file")
        user_data = provision_data.get("user_data")
        redeploy_cfg = provision_data.get("redeploy_cfg")
        authorized_keys = provision_data.get("authorized_keys")

        if not image_url:
            logger.error(
                "Please provide an image 'url' in the provision_data section"
            )
            raise ProvisioningError("No image url provided")

        if not user_data:
            logger.info("No user-data provided, using default user-data file")
            default_user_data = self.data_path / "default-user-data"

            if not default_user_data.exists():
                raise ProvisioningError("Default user-data file not found")
            shutil.copy(default_user_data, ATTACHMENTS_PROV_DIR)
            user_data = "default-user-data"

        # provision-image.sh expects specific filename,
        # so need to rename if doesn't match
        user_data_path = "user-data"
        self.copy_to_deploy_path(user_data, user_data_path)

        if redeploy_cfg is not None:
            redeploy_cfg_path = "redeploy.cfg"
            self.copy_to_deploy_path(redeploy_cfg, redeploy_cfg_path)
        if authorized_keys is not None:
            authorized_keys_path = "authorized_keys"
            self.copy_to_deploy_path(authorized_keys, authorized_keys_path)
        if token_file is not None:
            token_file_path = "url_token"
            self.copy_to_deploy_path(token_file, token_file_path)
        self.run_deploy_script(image_url)
        self.check_device_booted()

    def copy_to_deploy_path(self, source_path, dest_path):
        """
        Verify if attachment exists, then copy when
        it's missing in deployment dir
        """
        source_path = Path(source_path)
        if source_path.is_absolute():
            source_path = source_path.relative_to("/")
        source_path = ATTACHMENTS_PROV_DIR / source_path
        dest_path = ATTACHMENTS_PROV_DIR / dest_path

        if not source_path.exists():
            logger.error(
                f"{source_path} file was not found in attachments. "
                "Please check the filename."
            )
            raise ProvisioningError(
                f"{source_path} file was not found in attachments"
            )

        if not dest_path.exists():
            shutil.copy(source_path, dest_path)

    def run_deploy_script(self, image_url):
        """Run the script to deploy ISO and config files"""
        device_ip = self.config["device_ip"]

        logger.info("Running deployment script")

        deploy_script = self.data_path / "provision-image.sh"
        cmd = [
            deploy_script,
            "--iso-dut",
            image_url,
            "--local-config",
            ATTACHMENTS_PROV_DIR,
            device_ip,
        ]

        proc = subprocess.run(
            cmd,
            timeout=60 * 60,  # 1 hour - just in case
            check=False,
        )
        if proc.returncode:
            logger.error(
                "Deploy script failed with return code %s", proc.returncode
            )
            raise ProvisioningError("Deploy script failed")

    def test_ssh_access(self):
        """Verify SSH access available to DUT without any prompts"""
        try:
            test_username = self.job_data.get("test_data", {}).get(
                "test_username", "ubuntu"
            )
        except AttributeError:
            test_username = "ubuntu"

        cmd = [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            f"{test_username}@{self.config['device_ip']}",
            "true",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error("SSH connection failed: %s", result.stderr)
            raise ProvisioningError("Failed SSH to DUT")

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

    def check_device_booted(self):
        """Check to see if the device is booted and reachable with ssh"""
        logger.info("Checking to see if the device is available.")
        started = time.time()
        # Wait for provisioning to complete - can take a very long time
        while time.time() - started < 5400:
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
