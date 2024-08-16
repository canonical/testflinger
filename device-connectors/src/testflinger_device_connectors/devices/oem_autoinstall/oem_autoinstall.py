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
with image-deploy.sh script
"""

import json
import logging
import os
from pathlib import Path
import subprocess
import yaml
import shutil
import requests
from requests.auth import HTTPBasicAuth

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

    def provision(self):
        """Provision the device"""

        # Ensure the device is online and reachable
        try:
            self.test_ssh_access()
        except subprocess.CalledProcessError:
            self.hardreset()
            self.test_ssh_access()

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
            logger.error(
                "Please provide user-data file in provision_data section"
            )
            raise ProvisioningError("No user-data provided")

        # image-deploy.sh expects specific filename,
        # so need to rename if doesn't match
        user_data_path = "user-data"
        self.copy_to_deploy_path(user_data, user_data_path)

        if redeploy_cfg is not None:
            redeploy_cfg_path = "redeploy.cfg"
            self.copy_to_deploy_path(redeploy_cfg, redeploy_cfg_path)
        if authorized_keys is not None:
            authorized_keys_path = "authorized_keys"
            self.copy_to_deploy_path(authorized_keys, authorized_keys_path)

        try:
            image_file = self.download_with_credentials(
                image_url, ATTACHMENTS_PROV_DIR / token_file
            )
            self.run_deploy_script(image_file)
        finally:
            if image_file:
                os.unlink(image_file)

    def copy_to_deploy_path(self, source_path, dest_path):
        """
        Verify if attachment exists, then copy when
        it's missing in deployment dir
        """
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

    def run_deploy_script(self, image_file):
        """Run the script to deploy ISO and config files"""
        device_ip = self.config["device_ip"]

        data_path = Path(__file__).parent / "../../data/muxpi/oem_autoinstall"
        logger.info("Running deployment script")

        deploy_script = data_path / "image-deploy.sh"
        cmd = [
            deploy_script,
            "--iso",
            image_file,
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

    def download_with_credentials(self, url, token_file=None, filename=None):
        """
        Download a file from a URL
        If credentials file provided, then use token to auth.

        :param url: URL of the file to download.
        :param token_file: Optional path to the config file
         containing 'username' and 'token'.
        """
        logger.info("Downloading file from %s", url)
        if filename is None:
            filename = os.path.basename(url)

        # Use credentials if were provided
        auth = None
        if token_file:
            credentials = {}
            with open(token_file, "r") as file:
                for line in file:
                    key, value = line.strip().split(":", 1)
                    credentials[key.strip()] = value.strip()
            username = credentials.get("username")
            token = credentials.get("token")

            if username and token:
                auth = HTTPBasicAuth(username, token)
            else:
                logger.error("Credentials are missing in the config file.")
                return

        # Download the file
        try:
            response = requests.get(url, auth=auth)

            if response.status_code == 200:
                with open(filename, "wb") as file:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            file.write(chunk)
                return filename
            else:
                logger.error(
                    "Failed to download file: %s", response.status_code
                )
                logger.error("Failed response content: %s", response.text)

        except requests.RequestException as e:
            raise ProvisioningError(
                f"An error occurred in image download: {e}"
            )
