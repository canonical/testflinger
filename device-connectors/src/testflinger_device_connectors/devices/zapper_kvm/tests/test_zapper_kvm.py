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

import unittest
from unittest.mock import Mock, patch
from testflinger_device_connectors.devices.zapper_kvm import DeviceConnector


class ZapperKVMConnectorTests(unittest.TestCase):
    """Unit tests for ZapperConnector KVM class."""

    def test_validate_configuration(self):
        """
        Test whether the validate_configuration function returns
        the expected data merging the relevant bits from conf and job
        data.
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
            },
            "test_data": {
                "test_username": "username",
                "test_password": "password",
            },
        }

        connector._get_autoinstall_conf = Mock()
        args, kwargs = connector._validate_configuration()
        self.assertEqual(args, ())
        self.assertEqual(kwargs["url"], "http://example.com/image.iso")
        self.assertEqual(kwargs["username"], "username")
        self.assertEqual(kwargs["password"], "password")
        self.assertEqual(
            kwargs["autoinstall_conf"],
            connector._get_autoinstall_conf.return_value,
        )
        self.assertEqual(kwargs["reboot_script"], ["cmd1", "cmd2"])
        self.assertEqual(kwargs["device_ip"], "1.1.1.1")
        self.assertEqual(kwargs["robot_tasks"], ["job.robot", "another.robot"])

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

        with patch("builtins.open") as mock_open:
            conf = connector._get_autoinstall_conf()
        self.assertEqual(conf["storage_layout"], "lvm")
        self.assertIsNone(conf["storage_password"])
        self.assertNotIn("base_user_data", conf.keys())
        self.assertIn(
            mock_open.return_value.__enter__.return_value.read.return_value,
            conf["authorized_keys"],
        )

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
                "storage_password": "luks",
                "base_user_data": "base data content",
            },
            "test_data": {
                "test_username": "username",
                "test_password": "password",
            },
        }

        with patch("builtins.open") as mock_open:
            conf = connector._get_autoinstall_conf()
        self.assertEqual(conf["storage_layout"], "lvm")
        self.assertEqual(conf["storage_password"], "luks")
        self.assertEqual(conf["base_user_data"], "base data content")
        self.assertIn(
            mock_open.return_value.__enter__.return_value.read.return_value,
            conf["authorized_keys"],
        )
