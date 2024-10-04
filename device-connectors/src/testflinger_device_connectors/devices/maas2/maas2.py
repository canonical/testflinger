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

"""Ubuntu MaaS 2.x CLI support code."""

import base64
import json
import logging
import subprocess
import time
from collections import OrderedDict

import yaml

from testflinger_device_connectors.devices import (
    ProvisioningError,
    RecoveryError,
)
from testflinger_device_connectors.devices.maas2.maas_storage import (
    MaasStorage,
    MaasStorageError,
)


logger = logging.getLogger(__name__)


class Maas2:
    """Device Connector for Maas2."""

    def __init__(self, config, job_data):
        with open(config) as configfile:
            self.config = yaml.safe_load(configfile)
        with open(job_data) as j:
            self.job_data = json.load(j)
        self.maas_user = self.config.get("maas_user")
        self.node_id = self.config.get("node_id")
        self.agent_name = self.config.get("agent_name")
        self.timeout_min = int(self.config.get("timeout_min", 60))
        self.maas_storage = MaasStorage(self.maas_user, self.node_id)

    def _logger_debug(self, message):
        logger.debug("MAAS: {}".format(message))

    def _logger_info(self, message):
        logger.info("MAAS: {}".format(message))

    def _logger_warning(self, message):
        logger.warning("MAAS: {}".format(message))

    def _logger_error(self, message):
        logger.error("MAAS: {}".format(message))

    def _logger_critical(self, message):
        logger.critical("MAAS: {}".format(message))

    def recover(self):
        self._logger_info("Releasing node {}".format(self.agent_name))
        self.node_release()

    def provision(self):
        if self.config.get("reset_efi"):
            self.reset_efi()
        # Check if this is a device where we need to clear the tpm (dawson)
        if self.config.get("clear_tpm"):
            self.clear_tpm()
        provision_data = self.job_data.get("provision_data")
        # Default to a safe LTS if no distro is specified
        distro = provision_data.get("distro", "xenial")
        kernel = provision_data.get("kernel")
        user_data = provision_data.get("user_data")
        storage_data = provision_data.get("disks")
        self.deploy_node(distro, kernel, user_data, storage_data)

    def _install_efitools_snap(self):
        cmd = [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "ubuntu@{}".format(self.config["device_ip"]),
            "sudo snap install efi-tools-ijohnson --devmode --edge",
        ]
        subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False
        )
        cmd = [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "ubuntu@{}".format(self.config["device_ip"]),
            "sudo snap alias efi-tools-ijohnson.efibootmgr efibootmgr",
        ]
        subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False
        )

    def _get_efi_data(self):
        cmd = [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "ubuntu@{}".format(self.config["device_ip"]),
            "sudo efibootmgr -v",
        ]
        p = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False
        )
        # If it fails the first time, try installing efitools snap
        if p.returncode:
            self._install_efitools_snap()
            cmd = [
                "ssh",
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "UserKnownHostsFile=/dev/null",
                "ubuntu@{}".format(self.config["device_ip"]),
                "sudo efibootmgr -v",
            ]
            p = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
        if p.returncode:
            return None
        # Use OrderedDict because often the NIC entries in EFI are in a good
        # order with ipv4 ones coming first
        efi_data = OrderedDict()
        for line in p.stdout.decode().splitlines():
            k, v = line.split(" ", maxsplit=1)
            efi_data[k] = v
        return efi_data

    def _set_efi_data(self, boot_order):
        # Set the boot order to the comma separated string of entries
        self._logger_info("Setting boot order to {}".format(boot_order))
        cmd = [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "ubuntu@{}".format(self.config["device_ip"]),
            "sudo efibootmgr -o {}".format(boot_order),
        ]
        p = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False
        )
        if p.returncode:
            self._logger_error(
                'Failed to set efi boot order to "{}":\n'
                "{}".format(boot_order, p.stdout.decode())
            )

    def reset_efi(self):
        # Try to reset the boot order so that NICs boot first
        self._logger_info("Fixing EFI boot order before provisioning")
        efi_data = self._get_efi_data()
        if not efi_data:
            return
        bootlist = efi_data.get("BootOrder:").split(",")
        new_boot_order = []
        for k, v in efi_data.items():
            if ("IPv4" in v) and "Boot" in k:
                new_boot_order.append(k[4:8])
        for entry in bootlist:
            if entry not in new_boot_order:
                new_boot_order.append(entry)
        self._set_efi_data(",".join(new_boot_order))

    def clear_tpm(self):
        self._logger_info("Clearing the TPM before provisioning")
        # First see if we can run the command on the current install
        if self._run_tpm_clear_cmd():
            return
        # If not, then deploy bionic and try again
        self.deploy_node()
        if not self._run_tpm_clear_cmd():
            raise ProvisioningError("Failed to clear TPM")

    def _run_tpm_clear_cmd(self):
        # Run the command to clear the tpm over ssh
        cmd = [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "ubuntu@{}".format(self.config["device_ip"]),
            "echo 5 | sudo tee /sys/class/tpm/tpm0/ppi/request",
        ]
        proc = subprocess.run(cmd, timeout=30, check=False)
        if proc.returncode:
            return False

        cmd = [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "ubuntu@{}".format(self.config["device_ip"]),
            "cat /sys/class/tpm/tpm0/ppi/request",
        ]
        proc = subprocess.run(
            cmd, timeout=30, capture_output=True, check=False
        )
        if proc.returncode:
            return False

        # If we now see "5" in that file, then clearing tpm succeeded
        if proc.stdout.decode("utf-8").strip() == "5":
            return True
        return False

    def deploy_node(
        self, distro="bionic", kernel=None, user_data=None, storage_data=None
    ):
        # Deploy the node in maas, default to bionic if nothing is specified
        self.recover()
        status = self.node_status()
        # do not process an empty dataset
        if storage_data is not None:
            try:
                self.maas_storage.configure_node_storage(storage_data)
            except MaasStorageError as error:
                self._logger_error(
                    f"Unable to configure node storage: {error}"
                )
                raise ProvisioningError from error
        else:
            def_storage_data = self.config.get("default_disks")
            self._logger_debug(f"Using def storage data: {def_storage_data}")
            if not def_storage_data:
                self._logger_warning(
                    "'default_disks' and/or 'disks' unspecified; "
                    "setting default storage layout to flat"
                )
                self.set_flat_storage_layout()
            else:
                # reset to the default layout
                try:
                    self.maas_storage.configure_node_storage(
                        def_storage_data, reset=True
                    )
                except MaasStorageError as error:
                    self._logger_error(
                        "Unable to reset node storage to "
                        f"default_disk layout: {error}"
                    )
                    raise ProvisioningError from error

        self._logger_info("Acquiring node")
        cmd = [
            "maas",
            self.maas_user,
            "machines",
            "allocate",
            "system_id={}".format(self.node_id),
        ]
        # Do not use runcmd for this - we need the output, not the end user
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False
        )
        if proc.returncode:
            self._logger_error(f"maas error running: {' '.join(cmd)}")
            raise ProvisioningError(proc.stdout.decode())
        self._logger_info(
            "Starting node {} "
            "with distro {}".format(self.agent_name, distro)
        )
        cmd = [
            "maas",
            self.maas_user,
            "machine",
            "deploy",
            self.node_id,
            "distro_series={}".format(distro),
        ]
        if kernel:
            cmd.append("hwe_kernel={}".format(kernel))
        if user_data:
            data = base64.b64encode(user_data.encode()).decode()
            cmd.append("user_data={}".format(data))
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False
        )
        if proc.returncode:
            self._logger_error(f"maas-cli error running: {' '.join(cmd)}")
            raise ProvisioningError(proc.stdout.decode())

        # Make sure the device is available before returning
        minutes_spent = 0
        self._logger_info(
            "Timeout value: {} minutes.".format(self.timeout_min)
        )
        while minutes_spent < self.timeout_min:
            time.sleep(60)
            minutes_spent += 1
            self._logger_info(
                "{} minutes passed " "since deployment.".format(minutes_spent)
            )
            status = self.node_status()

            if status == "Failed deployment":
                self._logger_error("MaaS reports Failed Deployment")
                exception_msg = (
                    "Provisioning failed because "
                    + "MaaS got unexpected or "
                    + "deployment failure status signal."
                )
                raise ProvisioningError(exception_msg)

            if status == "Deployed":
                if self.check_test_image_booted():
                    self._logger_info("Deployed and booted.")
                    return

        self._logger_error(
            'Device {} still in "{}" state, deployment '
            "failed!".format(self.agent_name, status)
        )
        self._logger_error(proc.stdout.decode())
        exception_msg = (
            "Provisioning failed because deployment timeout. "
            + "Deploying for more than "
            + "{} minutes.".format(self.timeout_min)
        )
        raise ProvisioningError(exception_msg)

    def check_test_image_booted(self):
        self._logger_info("Checking if test image booted.")
        cmd = [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "ubuntu@{}".format(self.config["device_ip"]),
            "/bin/true",
        ]
        try:
            subprocess.run(
                cmd, stderr=subprocess.STDOUT, timeout=60, check=True
            )
        except subprocess.SubprocessError:
            return False
        # If we get here, then the above command proved we are booted
        return True

    def node_status(self):
        """Return status of the node according to maas:

        Ready: Node is unused
        Allocated: Node is allocated
        Deploying: Deployment in progress
        Deployed: Node is provisioned and ready for use
        """
        cmd = ["maas", self.maas_user, "machine", "read", self.node_id]
        # Do not use runcmd for this - we need the output, not the end user
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False
        )
        if proc.returncode:
            self._logger_error(f"maas error running: {' '.join(cmd)}")
            raise ProvisioningError(proc.stdout.decode())
        data = json.loads(proc.stdout.decode())
        return data.get("status_name")

    def node_release(self):
        """Release the node to make it available again"""
        cmd = ["maas", self.maas_user, "machine", "release", self.node_id]
        subprocess.run(cmd, check=False)
        # Make sure the device is available before returning
        for _ in range(0, 10):
            time.sleep(5)
            status = self.node_status()
            if status == "Ready":
                return
        self._logger_error(
            'Device {} still in "{}" state, could not '
            "recover!".format(self.agent_name, status)
        )
        raise RecoveryError("Device recovery failed!")

    def set_flat_storage_layout(self):
        """Reset to default flat storage layout"""
        cmd = [
            "maas",
            self.maas_user,
            "machine",
            "set-storage-layout",
            self.node_id,
            "storage_layout=flat",
        ]
        proc = subprocess.run(cmd, check=False)
        if proc.returncode:
            self._logger_error(
                "Unable to set flat disk layout, attempting to continue anyway"
            )
