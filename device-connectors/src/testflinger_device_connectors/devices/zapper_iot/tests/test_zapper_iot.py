import unittest
from unittest.mock import patch

from testflinger_device_connectors.devices import ProvisioningError
from testflinger_device_connectors.devices.zapper_iot import DeviceConnector


class ZapperIoTTests(unittest.TestCase):
    """Test Cases for the Zapper IoT class."""

    def test_validate_configuration(self):
        """
        Test the function creates a proper provision_data
        dictionary when valid data are provided.
        """

        device = DeviceConnector()
        device.job_data = {
            "provision_data": {
                "preset": "TestPreset",
                "urls": ["http://test.tar.gz"],
            }
        }
        device.config = {"reboot_script": ["cmd1", "cmd2"]}

        args, kwargs = device._validate_configuration()

        expected = {
            "username": "ubuntu",
            "password": "ubuntu",
            "preset": "TestPreset",
            "reboot_script": ["cmd1", "cmd2"],
            "urls": ["http://test.tar.gz"],
        }

        self.assertEqual(args, ())
        self.assertDictEqual(kwargs, expected)

    def test_validate_configuration_provision_plan(self):
        """
        Test the function validates a custom test plan
        when provided.
        """

        device = DeviceConnector()
        device.job_data = {
            "provision_data": {
                "provision_plan": {
                    "config": {
                        "project_name": "name",
                        "username": "admin",
                        "password": "admin",
                        "serial_console": {
                            "port": "/dev/ttySanity1",
                            "baud_rate": 115200,
                        },
                        "network": "eth0",
                    },
                    "run_stage": [
                        {"initial_login": {"method": "system-user"}},
                    ],
                }
            }
        }
        device.config = {"reboot_script": ["cmd1", "cmd2"]}

        args, kwargs = device._validate_configuration()

        expected = {
            "username": "ubuntu",
            "password": "ubuntu",
            "custom_provision_plan": {
                "config": {
                    "project_name": "name",
                    "username": "ubuntu",  # this gets overridden
                    "password": "ubuntu",
                    "serial_console": {
                        "port": "/dev/ttySanity1",
                        "baud_rate": 115200,
                    },
                    "network": "eth0",
                },
                "run_stage": [
                    {"initial_login": {"method": "system-user"}},
                ],
            },
            "urls": [],
            "reboot_script": ["cmd1", "cmd2"],
            "preset": None,
        }
        self.maxDiff = None
        self.assertEqual(args, ())
        self.assertDictEqual(expected, kwargs)

    def test_validate_configuration_invalid_url(self):
        """
        Test the function raises an exception if one of
        the url is not valid.
        """

        device = DeviceConnector()
        device.job_data = {
            "provision_data": {
                "urls": ["not-a-url"],
            }
        }
        device.config = {"reboot_script": ["cmd1", "cmd2"]}

        with self.assertRaises(ProvisioningError):
            device._validate_configuration()

    def test_validate_configuration_invalid_provision_plan(self):
        """
        Test the function raises an exception if the
        provided custom testplan is not valid.
        """

        device = DeviceConnector()
        device.job_data = {
            "provision_data": {"provision_plan": {"key1": "value1"}}
        }
        device.config = {"reboot_script": []}

        with self.assertRaises(ProvisioningError):
            device._validate_configuration()

    @patch.object(DeviceConnector, "_copy_ssh_id")
    def test_post_run_actions_copy_ssh_id(self, mock_copy_ssh_id):
        """
        Test the function copies the ssh id if the
        initial login method is Not console-conf.
        """

        device = DeviceConnector()
        device.job_data = {
            "provision_data": {
                "provision_plan": {
                    "run_stage": [{"initial_login": {"method": "system-user"}}]
                }
            }
        }
        device._post_run_actions(args=None)

        mock_copy_ssh_id.assert_called_once()

    @patch.object(DeviceConnector, "_copy_ssh_id")
    def test_post_run_actions_no_copy_ssh_id(self, mock_copy_ssh_id):
        """
        Test the function does not copy the ssh id if the
        initial login method is console-conf.
        """

        device = DeviceConnector()
        device.job_data = {
            "provision_data": {
                "provision_plan": {
                    "run_stage": [
                        {"initial_login": {"method": "console-conf"}}
                    ]
                }
            }
        }
        device._post_run_actions(args=None)
        mock_copy_ssh_id.assert_not_called()
