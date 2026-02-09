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
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests
import yaml
from typing_extensions import override

from testflinger_device_connectors.devices import ProvisioningError
from testflinger_device_connectors.devices.dell_oemscript import DellOemScript
from testflinger_device_connectors.devices.hp_oemscript import HPOemScript
from testflinger_device_connectors.devices.lenovo_oemscript import (
    LenovoOemScript,
)
from testflinger_device_connectors.devices.oemscript import OemScript
from testflinger_device_connectors.devices.zapper import ZapperConnector

logger = logging.getLogger(__name__)


class DeviceConnector(ZapperConnector):
    """Tool for provisioning baremetal with a given image."""

    PROVISION_METHOD = "ProvisioningKVM"

    @override
    def pre_provision_hook(self):
        """Power off the DUT via the Zapper REST API before provisioning.

        If the REST API is not available, fall back to the default
        pre-provision hook (SSH-based control host check).
        """
        control_host = self.config.get("control_host", "")
        if not control_host:
            return super().pre_provision_hook()

        try:
            logger.info("Attempt to power cycle the control host.")
            self._api_post("/api/v1/system/poweroff", timeout=10)
            with contextlib.suppress(TimeoutError):
                ZapperConnector.wait_online(
                    ZapperConnector._check_rpyc_server_on_host,
                    control_host,
                    30,
                )
            self._reboot_control_host()
            self.wait_ready(control_host)
        except requests.RequestException:
            logger.warning(
                "The REST API is not available on %s, "
                "falling back to default pre-provision hook",
                control_host,
            )
            super().pre_provision_hook()

    def _validate_base_user_data(self, encoded_user_data: str):
        """Assert `base_user_data` argument is a valid base64 encoded YAML."""
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
        """Autoinstall-related keys are pre-fixed with `autoinstall_`.

        If any of those arguments are provided and valid, the function
        returns an autoinstall_conf dictionary, including the agent
        SSH public key.
        """
        autoinstall_conf = {}

        if self.job_data["provision_data"].get("autoinstall_oem"):
            # In case of Ubuntu OEM via autoinstall, use a
            # dedicated user-data file as base.

            logger.info(
                "When using 'autoinstall_oem', "
                "other autoinstall keys are not considered"
            )

            user_data_oem = (
                Path(__file__).parent / "../../data/zapper_kvm/user-data-oem"
            )
            user_data = user_data_oem.read_text(encoding="utf-8")
            encoded_user_data = base64.b64encode(user_data.encode()).decode()

            user_data = yaml.safe_load(user_data)
            storage = user_data["autoinstall"]["storage"]["layout"]["name"]

            autoinstall_conf = {
                "base_user_data": encoded_user_data,
                "storage_layout": storage,
            }

        else:
            for key, value in self.job_data["provision_data"].items():
                if "autoinstall_" not in key:
                    continue

                autoinstall_key = key.replace("autoinstall_", "")
                with contextlib.suppress(AttributeError):
                    getattr(self, f"_validate_{autoinstall_key}")(value)
                autoinstall_conf[autoinstall_key] = value

        if not autoinstall_conf:
            logger.info("Autoinstall-related keys were not provided.")
            return None

        autoinstall_conf["authorized_keys"] = [self._read_ssh_key()]

        return autoinstall_conf

    def _read_ssh_key(self) -> str:
        return (
            Path("~/.ssh/id_rsa.pub").expanduser().read_text(encoding="utf-8")
        )

    def _get_credentials(self, target: str | None = None) -> tuple[str, str]:
        if target == "jammy-oem":
            return "ubuntu", "u"
        else:
            return (
                self.job_data.get("test_data", {}).get(
                    "test_username", "ubuntu"
                ),
                self.job_data.get("test_data", {}).get(
                    "test_password", "ubuntu"
                ),
            )

    def _validate_configuration(
        self,
    ) -> Tuple[Tuple, Dict[str, Any]]:
        """Validate the job config and data and prepare the arguments
        for the Zapper `provision` API.
        """
        provisioning_data = {}
        if "preset" in self.job_data["provision_data"]:
            has_autoinstall = False
            for key, value in self.job_data["provision_data"].items():
                if key.startswith("autoinstall"):
                    has_autoinstall = True
                else:
                    provisioning_data[key] = value

            provisioning_data["username"], provisioning_data["password"] = (
                self._get_credentials("preset")
            )

            if has_autoinstall:
                provisioning_data["autoinstall_conf"] = (
                    self._get_autoinstall_conf()
                )

        elif "alloem_url" in self.job_data["provision_data"]:
            provisioning_data["url"] = self.job_data["provision_data"][
                "alloem_url"
            ]
            provisioning_data["username"], provisioning_data["password"] = (
                self._get_credentials("jammy-oem")
            )
            provisioning_data["robot_retries"] = max(
                2, self.job_data["provision_data"].get("robot_retries", 1)
            )
            provisioning_data["autoinstall_conf"] = (
                self._get_autoinstall_conf()
            )
            provisioning_data["robot_tasks"] = self.job_data["provision_data"][
                "robot_tasks"
            ]
        else:
            provisioning_data["url"] = self.job_data["provision_data"]["url"]
            provisioning_data["username"], provisioning_data["password"] = (
                self._get_credentials()
            )
            provisioning_data["robot_retries"] = self.job_data[
                "provision_data"
            ].get("robot_retries", 1)
            provisioning_data["autoinstall_conf"] = (
                self._get_autoinstall_conf()
            )
            provisioning_data["robot_tasks"] = self.job_data["provision_data"][
                "robot_tasks"
            ]

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
        """If "alloem_url" was in scope, the Zapper only restored
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
