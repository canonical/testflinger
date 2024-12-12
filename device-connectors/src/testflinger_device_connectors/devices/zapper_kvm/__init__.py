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

"""Zapper Connector for KVM provisioning."""

import base64
import binascii
import contextlib
import logging
import os
import subprocess
from typing import Any, Dict, Optional, Tuple

import yaml
from testflinger_device_connectors.devices import ProvisioningError
from testflinger_device_connectors.devices.zapper import ZapperConnector
from testflinger_device_connectors.devices.oemscript import OemScript
from testflinger_device_connectors.devices.lenovo_oemscript import (
    LenovoOemScript,
)
from testflinger_device_connectors.devices.dell_oemscript import DellOemScript
from testflinger_device_connectors.devices.hp_oemscript import HPOemScript

logger = logging.getLogger(__name__)


class DeviceConnector(ZapperConnector):
    """Tool for provisioning baremetal with a given image."""

    PROVISION_METHOD = "ProvisioningKVM"

    def _validate_base_user_data(self, encoded_user_data: str):
        """
        Assert `base_user_data` argument is a valid base64 encoded YAML.
        """
        try:
            user_data = base64.b64decode(encoded_user_data.encode()).decode()
            yaml.safe_load(user_data)
        except (binascii.Error, ValueError) as exc:
            raise ProvisioningError(
                "Provided `base_user_data` is not base64 encoded."
            ) from exc
        except yaml.YAMLError as exc:
            raise ProvisioningError(
                "Provided `base_user_data` is not a valid YAML."
            ) from exc

    def _get_autoinstall_conf(self) -> Optional[Dict[str, Any]]:
        """
        Autoinstall-related keys are pre-fixed with `autoinstall_`.

        If any of those arguments are provided and valid, the function
        returns an autoinstall_conf dictionary, including the agent
        SSH public key.
        """

        autoinstall_conf = {}
        for key, value in self.job_data["provision_data"].items():
            if "autoinstall_" not in key:
                continue

            key = key.replace("autoinstall_", "")
            with contextlib.suppress(AttributeError):
                getattr(self, f"_validate_{key}")(value)

            autoinstall_conf[key] = value

        if not autoinstall_conf:
            logger.info("Autoinstall-related keys were not provided.")
            return None

        with open(os.path.expanduser("~/.ssh/id_rsa.pub")) as pub:
            autoinstall_conf["authorized_keys"] = [pub.read()]

        return autoinstall_conf

    def _validate_configuration(
        self,
    ) -> Tuple[Tuple, Dict[str, Any]]:
        """
        Validate the job config and data and prepare the arguments
        for the Zapper `provision` API.
        """

        if "alloem_url" in self.job_data["provision_data"]:
            url = self.job_data["provision_data"]["alloem_url"]
            username = "ubuntu"
            password = "u"
            retries = max(
                2, self.job_data["provision_data"].get("robot_retries", 1)
            )
        else:
            url = self.job_data["provision_data"]["url"]
            username = self.job_data.get("test_data", {}).get(
                "test_username", "ubuntu"
            )
            password = self.job_data.get("test_data", {}).get(
                "test_password", "ubuntu"
            )
            retries = self.job_data["provision_data"].get("robot_retries", 1)

        provisioning_data = {
            "url": url,
            "username": username,
            "password": password,
            "robot_retries": retries,
            "autoinstall_conf": self._get_autoinstall_conf(),
            "reboot_script": self.config["reboot_script"],
            "device_ip": self.config["device_ip"],
            "robot_tasks": self.job_data["provision_data"]["robot_tasks"],
        }

        # Let's handle defaults on the Zapper side adding only the explicitly
        # specified keys to the `provision_data` dict.
        optionals = [
            "cmdline_append",
            "skip_download",
            "wait_until_ssh",
            "live_image",
            "ubuntu_sso_email",
        ]
        provisioning_data.update(
            {
                opt: self.job_data["provision_data"][opt]
                for opt in optionals
                if opt in self.job_data["provision_data"]
            }
        )

        return ((), provisioning_data)

    def _post_run_actions(self, args):
        super()._post_run_actions(args)

        if "alloem_url" in self.job_data["provision_data"]:
            self._post_run_actions_oem(args)

    def _post_run_actions_oem(self, args):
        """Post run actions for 22.04 OEM images."""
        try:
            self._change_password("ubuntu", "u")
            self._copy_ssh_id()
        except subprocess.CalledProcessError as exc:
            logger.error("Process failed with: %s", exc.output.decode())
            raise ProvisioningError(
                "Failed configuring SSH on the DUT."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise ProvisioningError(
                "Timed out configuring SSH on the DUT."
            ) from exc

        self._run_oem_script(args)

    def _run_oem_script(self, args):
        """
        If "alloem_url" was in scope, the Zapper only restored
        the OEM reset partition. The usual oemscript will take care
        of the rest.
        """

        if not self.job_data["provision_data"].get("url"):
            logger.warning(
                "Provisioned with base `alloem` image, no test URL specified."
            )
            return

        oem = self.job_data["provision_data"].get("oem")
        oemscript = {
            "hp": HPOemScript,
            "dell": DellOemScript,
            "lenovo": LenovoOemScript,
        }.get(oem, OemScript)(args.config, args.job_data)

        oemscript.provision()

    def _change_password(self, username, orig_password):
        """Change password via SSH to the one specified in the job data."""

        password = self.job_data.get("test_data", {}).get(
            "test_password", "ubuntu"
        )
        logger.info("Changing the original password to %s", password)

        cmd = [
            "sshpass",
            "-p",
            orig_password,
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            f"{username}@{self.config['device_ip']}",
            f"echo 'ubuntu:{password}' | sudo chpasswd",
        ]

        subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=60)
