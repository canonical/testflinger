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

"""Control host connector for KVM provisioning.

The provisioning payload is built by the control host service; this connector
is a thin client that submits the job and runs the OEM-specific post-run
actions that remain an agent responsibility.
"""

import logging
import subprocess

from testflinger_device_connectors.devices import ProvisioningError
from testflinger_device_connectors.devices.control_host import (
    ControlHostConnector,
)
from testflinger_device_connectors.devices.dell_oemscript import DellOemScript
from testflinger_device_connectors.devices.hp_oemscript import HPOemScript
from testflinger_device_connectors.devices.lenovo_oemscript import (
    LenovoOemScript,
)
from testflinger_device_connectors.devices.oemscript import OemScript

logger = logging.getLogger(__name__)

JAMMY_OEM_PRESET = "desktop-jammy-oem"


class DeviceConnector(ControlHostConnector):
    """Tool for provisioning baremetal with a given image."""

    PROVISION_METHOD = "kvm"

    def _post_run_actions(self, args):
        provision_data = self.job_data["provision_data"]
        used_alloem = "alloem_url" in provision_data
        is_jammy_oem_preset = provision_data.get("preset") == JAMMY_OEM_PRESET

        if used_alloem or is_jammy_oem_preset:
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
        """If "alloem_url" was in scope, the control host only restored
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
