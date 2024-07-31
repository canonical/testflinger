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
"""Unit tests for Zapper KVM device connector."""

import subprocess
import unittest
from unittest.mock import Mock, patch, mock_open
from testflinger_device_connectors.devices import ProvisioningError
from testflinger_device_connectors.devices.zapper_kvm import DeviceConnector


class ZapperKVMConnectorTests(unittest.TestCase):
    """Unit tests for ZapperConnector KVM class."""

    def test_validate_configuration(self):
        """
        Test whether the validate_configuration function returns
        the expected data merging the relevant bits from conf and job
        data when passing only the required arguments
        """

        connector = DeviceConnector()
        connector.config = {
            "device_ip": "1.1.1.1",
            "control_host": "1.1.1.2",
            "reboot_script": ["cmd1", "cmd2"],
        }
        connector.job_data = {
            "job_queue": "queue",
            "provision_data": {
                "url": "http://example.com/image.iso",
                "robot_tasks": [
                    "job.robot",
                    "another.robot",
                ],
            },
        }

        connector._get_autoinstall_conf = Mock()
        args, kwargs = connector._validate_configuration()

        expected = {
            "url": "http://example.com/image.iso",
            "username": "ubuntu",
            "password": "ubuntu",
            "autoinstall_conf": connector._get_autoinstall_conf.return_value,
            "reboot_script": ["cmd1", "cmd2"],
            "device_ip": "1.1.1.1",
            "robot_tasks": ["job.robot", "another.robot"],
            "robot_retries": 1,
        }
        self.assertEqual(args, ())
        self.assertDictEqual(kwargs, expected)

    def test_validate_configuration_w_opt(self):
        """
        Test whether the validate_configuration function returns
        the expected data merging the relevant bits from conf and job
        data when passing all the optional arguments.
        """

        connector = DeviceConnector()
        connector.config = {
            "device_ip": "1.1.1.1",
            "control_host": "1.1.1.2",
            "reboot_script": ["cmd1", "cmd2"],
        }
        connector.job_data = {
            "job_queue": "queue",
            "provision_data": {
                "url": "http://example.com/image.iso",
                "robot_tasks": [
                    "job.robot",
                    "another.robot",
                ],
                "storage_layout": "lvm",
                "robot_retries": 3,
                "cmdline_append": "more arguments",
                "skip_download": True,
                "wait_until_ssh": True,
                "live_image": False,
            },
            "test_data": {
                "test_username": "username",
                "test_password": "password",
            },
        }

        connector._get_autoinstall_conf = Mock()
        args, kwargs = connector._validate_configuration()

        expected = {
            "url": "http://example.com/image.iso",
            "username": "username",
            "password": "password",
            "autoinstall_conf": connector._get_autoinstall_conf.return_value,
            "reboot_script": ["cmd1", "cmd2"],
            "device_ip": "1.1.1.1",
            "robot_tasks": ["job.robot", "another.robot"],
            "robot_retries": 3,
            "cmdline_append": "more arguments",
            "skip_download": True,
            "wait_until_ssh": True,
            "live_image": False,
        }
        self.assertEqual(args, ())
        self.assertDictEqual(kwargs, expected)

    def test_validate_configuration_alloem(self):
        """
        Test whether the validate_configuration function returns
        the expected data merging the relevant bits from conf and job
        data when `alloem_url` is passed. In that case, username and
        password are hardcoded and the Zapper shall try the procedures
        at least twice because it can fail on purpose.
        """

        connector = DeviceConnector()
        connector.config = {
            "device_ip": "1.1.1.1",
            "control_host": "1.1.1.2",
            "reboot_script": ["cmd1", "cmd2"],
        }
        connector.job_data = {
            "job_queue": "queue",
            "provision_data": {
                "url": "http://example.com/image.iso",
                "alloem_url": "http://example.com/alloem.iso",
                "robot_tasks": [
                    "job.robot",
                    "another.robot",
                ],
                "storage_layout": "lvm",
            },
            "test_data": {
                "test_username": "username",
                "test_password": "password",
            },
        }

        connector._get_autoinstall_conf = Mock()
        args, kwargs = connector._validate_configuration()

        expected = {
            "url": "http://example.com/alloem.iso",
            "username": "ubuntu",
            "password": "u",
            "autoinstall_conf": connector._get_autoinstall_conf.return_value,
            "reboot_script": ["cmd1", "cmd2"],
            "device_ip": "1.1.1.1",
            "robot_tasks": ["job.robot", "another.robot"],
            "robot_retries": 2,
        }
        self.assertEqual(args, ())
        self.assertDictEqual(kwargs, expected)

    def test_get_autoinstall_none(self):
        """
        Test whether the get_autoinstall_conf function returns
        None in case the storage_layout is not specified.
        """

        connector = DeviceConnector()
        connector.job_data = {
            "job_queue": "queue",
            "provision_data": {
                "url": "http://example.com/image.iso",
                "robot_tasks": [
                    "job.robot",
                    "another.robot",
                ],
            },
            "test_data": {
                "test_username": "username",
                "test_password": "password",
            },
        }

        with patch("builtins.open", mock_open(read_data="mykey")):
            conf = connector._get_autoinstall_conf()

        self.assertIsNone(conf)

    def test_get_autoinstall_conf(self):
        """
        Test whether the get_autoinstall_conf function returns
        the expected data merging the relevant bits from conf and job
        data when password and base_user_data are not given.
        """

        connector = DeviceConnector()
        connector.job_data = {
            "job_queue": "queue",
            "provision_data": {
                "url": "http://example.com/image.iso",
                "robot_tasks": [
                    "job.robot",
                    "another.robot",
                ],
                "storage_layout": "lvm",
            },
            "test_data": {
                "test_username": "username",
                "test_password": "password",
            },
        }

        with patch("builtins.open", mock_open(read_data="mykey")):
            conf = connector._get_autoinstall_conf()

        expected = {
            "storage_layout": "lvm",
            "authorized_keys": ["mykey"],
        }
        self.assertDictEqual(conf, expected)

    def test_get_autoinstall_conf_full(self):
        """
        Test whether the get_autoinstall_conf function returns
        the expected data merging the relevant bits from conf and job
        data when password and user_data_base are given.
        """

        connector = DeviceConnector()
        connector.job_data = {
            "job_queue": "queue",
            "provision_data": {
                "url": "http://example.com/image.iso",
                "robot_tasks": [
                    "job.robot",
                    "another.robot",
                ],
                "storage_layout": "lvm",
                "base_user_data": "base data content",
            },
            "test_data": {
                "test_username": "username",
                "test_password": "password",
            },
        }

        with patch("builtins.open", mock_open(read_data="mykey")):
            conf = connector._get_autoinstall_conf()

        expected = {
            "storage_layout": "lvm",
            "base_user_data": "base data content",
            "authorized_keys": ["mykey"],
        }
        self.assertDictEqual(conf, expected)

    def test_run_oem_no_url(self):
        """
        Test the function returns without further action when URL
        is not specified.
        """

        connector = DeviceConnector()
        connector.job_data = {"provision_data": {}}

        with patch(
            "testflinger_device_connectors.devices.zapper_kvm.OemScript"
        ) as script:
            connector._run_oem_script("args")

        script.assert_not_called()

    def test_run_oem_default(self):
        """Test the function runs the base OemScript."""

        connector = DeviceConnector()
        connector.job_data = {"provision_data": {"url": "file://image.iso"}}
        args = Mock()

        with patch(
            "testflinger_device_connectors.devices.zapper_kvm.OemScript"
        ) as script:
            connector._run_oem_script(args)

        script.assert_called_with(args.config, args.job_data)
        script.return_value.provision.assert_called_once()

    def test_run_oem_hp(self):
        """Test the function runs the HP OemScript when oem=hp."""

        connector = DeviceConnector()
        connector.job_data = {
            "provision_data": {"url": "file://image.iso", "oem": "hp"}
        }
        args = Mock()

        with patch(
            "testflinger_device_connectors.devices.zapper_kvm.HPOemScript"
        ) as script:
            connector._run_oem_script(args)

        script.assert_called_with(args.config, args.job_data)
        script.return_value.provision.assert_called_once()

    def test_run_oem_dell(self):
        """Test the function runs the Dell OemScript when oem=dell."""

        connector = DeviceConnector()
        connector.job_data = {
            "provision_data": {"url": "file://image.iso", "oem": "dell"}
        }
        args = Mock()

        with patch(
            "testflinger_device_connectors.devices.zapper_kvm.DellOemScript"
        ) as script:
            connector._run_oem_script(args)

        script.assert_called_with(args.config, args.job_data)
        script.return_value.provision.assert_called_once()

    def test_run_oem_lenovo(self):
        """Test the function runs the Lenovo OemScript when oem=lenovo."""

        connector = DeviceConnector()
        connector.job_data = {
            "provision_data": {"url": "file://image.iso", "oem": "lenovo"}
        }
        args = Mock()

        with patch(
            "testflinger_device_connectors.devices.zapper_kvm.LenovoOemScript"
        ) as script:
            connector._run_oem_script(args)

        script.assert_called_with(args.config, args.job_data)
        script.return_value.provision.assert_called_once()

    @patch("subprocess.check_output")
    def test_change_password(self, mock_check_output):
        """
        Test the function runs a command over SSH to change the
        original password to the one specified in test_data.
        """
        connector = DeviceConnector()
        connector.job_data = {"test_data": {"test_password": "new_password"}}
        connector.config = {"device_ip": "localhost"}

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
        """
        Test the function updates the password and run the OEM script
        when `alloem_url` is in scope.
        """
        connector = DeviceConnector()
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

    def test_post_run_actions_alloem_error(self):
        """
        Test the function raises the ProvisioningError
        exception in case one of the SSH commands fail.
        """
        connector = DeviceConnector()
        connector.job_data = {
            "provision_data": {"alloem_url": "file://image.iso"}
        }

        connector._copy_ssh_id = Mock()
        connector._change_password = Mock()
        connector._run_oem_script = Mock()

        connector._copy_ssh_id.side_effect = subprocess.CalledProcessError(
            1, "", "A bad error".encode()
        )
        connector._change_password.side_effect = None

        with self.assertRaises(ProvisioningError):
            connector._post_run_actions("args")

        connector._copy_ssh_id.side_effect = None
        connector._change_password.side_effect = subprocess.CalledProcessError(
            1, "", "A bad error".encode()
        )

        with self.assertRaises(ProvisioningError):
            connector._post_run_actions("args")

    def test_post_run_actions_alloem_timeout(self):
        """
        Test the function raises the ProvisioningError
        exception in case one of the SSH commands times out.
        """
        connector = DeviceConnector()
        connector.job_data = {
            "provision_data": {"alloem_url": "file://image.iso"}
        }
        connector._copy_ssh_id = Mock()
        connector._change_password = Mock()
        connector._run_oem_script = Mock()

        connector._copy_ssh_id.side_effect = subprocess.TimeoutExpired("", 1)
        connector._change_password.side_effect = None

        with self.assertRaises(ProvisioningError):
            connector._post_run_actions("args")

        connector._copy_ssh_id.side_effect = None
        connector._change_password.side_effect = subprocess.TimeoutExpired(
            "", 1
        )

        with self.assertRaises(ProvisioningError):
            connector._post_run_actions("args")
