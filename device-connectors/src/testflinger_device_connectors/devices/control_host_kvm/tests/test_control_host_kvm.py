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
"""Unit tests for the control host KVM device connector."""

import subprocess
import unittest
from unittest.mock import Mock, patch

from testflinger_device_connectors.devices import ProvisioningError
from testflinger_device_connectors.devices.control_host_kvm import (
    DeviceConnector,
)


class ControlHostKVMConnectorTests(unittest.TestCase):
    """Unit tests for the control host KVM connector."""

    def test_provision_method(self):
        self.assertEqual(DeviceConnector.PROVISION_METHOD, "kvm")

    def test_does_not_manage_dut_power_during_reboot(self) -> None:
        """control_host_kvm must NOT power cycle the DUT while the control
        host reboots; only control_host_iot opts in.
        """
        self.assertFalse(DeviceConnector.MANAGE_DUT_POWER_DURING_REBOOT)

    def test_run_oem_no_url(self):
        """Test the function returns without further action when URL
        is not specified.
        """
        connector = DeviceConnector(
            {"device_ip": "1.1.1.1", "control_host": "1.1.1.2"}
        )
        connector.job_data = {"provision_data": {}}

        with patch(
            "testflinger_device_connectors.devices.control_host_kvm.OemScript"
        ) as script:
            connector._run_oem_script("args")

        script.assert_not_called()

    def test_run_oem_default(self):
        """Test the function runs the base OemScript."""
        connector = DeviceConnector(
            {"device_ip": "1.1.1.1", "control_host": "1.1.1.2"}
        )
        connector.job_data = {"provision_data": {"url": "file://image.iso"}}
        args = Mock()

        with patch(
            "testflinger_device_connectors.devices.control_host_kvm.OemScript"
        ) as script:
            connector._run_oem_script(args)

        script.assert_called_with(args.config, args.job_data)
        script.return_value.provision.assert_called_once()

    def test_run_oem_hp(self):
        connector = DeviceConnector(
            {"device_ip": "1.1.1.1", "control_host": "1.1.1.2"}
        )
        connector.job_data = {
            "provision_data": {"url": "file://image.iso", "oem": "hp"}
        }
        args = Mock()

        with patch(
            "testflinger_device_connectors.devices.control_host_kvm"
            ".HPOemScript"
        ) as script:
            connector._run_oem_script(args)

        script.assert_called_with(args.config, args.job_data)
        script.return_value.provision.assert_called_once()

    def test_run_oem_dell(self):
        connector = DeviceConnector(
            {"device_ip": "1.1.1.1", "control_host": "1.1.1.2"}
        )
        connector.job_data = {
            "provision_data": {"url": "file://image.iso", "oem": "dell"}
        }
        args = Mock()

        with patch(
            "testflinger_device_connectors.devices.control_host_kvm"
            ".DellOemScript"
        ) as script:
            connector._run_oem_script(args)

        script.assert_called_with(args.config, args.job_data)
        script.return_value.provision.assert_called_once()

    def test_run_oem_lenovo(self):
        connector = DeviceConnector(
            {"device_ip": "1.1.1.1", "control_host": "1.1.1.2"}
        )
        connector.job_data = {
            "provision_data": {"url": "file://image.iso", "oem": "lenovo"}
        }
        args = Mock()

        with patch(
            "testflinger_device_connectors.devices.control_host_kvm"
            ".LenovoOemScript"
        ) as script:
            connector._run_oem_script(args)

        script.assert_called_with(args.config, args.job_data)
        script.return_value.provision.assert_called_once()

    @patch("subprocess.check_output")
    def test_change_password(self, mock_check_output):
        """Test the function runs a command over SSH to change the
        original password to the one specified in test_data.
        """
        connector = DeviceConnector(
            {"device_ip": "localhost", "control_host": "control-host"}
        )
        connector.job_data = {"test_data": {"test_password": "new_password"}}

        connector._change_password("ubuntu", "u")

        cmd = [
            "sshpass",
            "-p",
            "u",
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "ubuntu@localhost",
            "echo 'ubuntu:new_password' | sudo chpasswd",
        ]
        mock_check_output.assert_called_with(
            cmd, stderr=subprocess.STDOUT, timeout=60
        )

    def test_post_run_actions_alloem(self):
        """Test the function updates the password and runs the OEM script
        when `alloem_url` is in scope.
        """
        connector = DeviceConnector(
            {"device_ip": "localhost", "control_host": "control-host"}
        )
        connector.job_data = {
            "provision_data": {"alloem_url": "file://image.iso"}
        }
        connector._copy_ssh_id = Mock()
        connector._change_password = Mock()
        connector._run_oem_script = Mock()

        connector._post_run_actions("args")

        connector._change_password.assert_called_with("ubuntu", "u")
        connector._run_oem_script.assert_called_with("args")
        connector._copy_ssh_id.assert_called()

    def test_post_run_actions_jammy_oem_preset(self):
        """Test the function updates the password and runs the OEM script
        when the `desktop-jammy-oem` preset is in scope.
        """
        connector = DeviceConnector(
            {"device_ip": "localhost", "control_host": "control-host"}
        )
        connector.job_data = {
            "provision_data": {"preset": "desktop-jammy-oem"}
        }
        connector._copy_ssh_id = Mock()
        connector._change_password = Mock()
        connector._run_oem_script = Mock()

        connector._post_run_actions("args")

        connector._change_password.assert_called_with("ubuntu", "u")
        connector._run_oem_script.assert_called_with("args")
        connector._copy_ssh_id.assert_called()

    def test_post_run_actions_no_oem_noop(self):
        """Without alloem/jammy-oem, no OEM post-run actions run."""
        connector = DeviceConnector(
            {"device_ip": "localhost", "control_host": "control-host"}
        )
        connector.job_data = {"provision_data": {"url": "file://image.iso"}}
        connector._copy_ssh_id = Mock()
        connector._change_password = Mock()
        connector._run_oem_script = Mock()

        connector._post_run_actions("args")

        connector._change_password.assert_not_called()
        connector._run_oem_script.assert_not_called()
        connector._copy_ssh_id.assert_not_called()

    def test_post_run_actions_alloem_error(self):
        """Test the function raises ProvisioningError if an SSH command
        fails.
        """
        connector = DeviceConnector(
            {"device_ip": "localhost", "control_host": "control-host"}
        )
        connector.job_data = {
            "provision_data": {"alloem_url": "file://image.iso"}
        }
        connector._copy_ssh_id = Mock()
        connector._change_password = Mock()
        connector._run_oem_script = Mock()

        connector._copy_ssh_id.side_effect = subprocess.CalledProcessError(
            1, "", "A bad error".encode()
        )
        with self.assertRaises(ProvisioningError):
            connector._post_run_actions("args")

        connector._copy_ssh_id.side_effect = None
        connector._change_password.side_effect = subprocess.CalledProcessError(
            1, "", "A bad error".encode()
        )
        with self.assertRaises(ProvisioningError):
            connector._post_run_actions("args")

    def test_post_run_actions_alloem_timeout(self):
        """Test the function raises ProvisioningError if an SSH command
        times out.
        """
        connector = DeviceConnector(
            {"device_ip": "localhost", "control_host": "control-host"}
        )
        connector.job_data = {
            "provision_data": {"alloem_url": "file://image.iso"}
        }
        connector._copy_ssh_id = Mock()
        connector._change_password = Mock()
        connector._run_oem_script = Mock()

        connector._copy_ssh_id.side_effect = subprocess.TimeoutExpired("", 1)
        with self.assertRaises(ProvisioningError):
            connector._post_run_actions("args")

        connector._copy_ssh_id.side_effect = None
        connector._change_password.side_effect = subprocess.TimeoutExpired(
            "", 1
        )
        with self.assertRaises(ProvisioningError):
            connector._post_run_actions("args")


if __name__ == "__main__":
    unittest.main()
