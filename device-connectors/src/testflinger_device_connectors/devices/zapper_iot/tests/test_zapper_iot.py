import unittest
from unittest.mock import patch

from testflinger_device_connectors.devices import ProvisioningError
from testflinger_device_connectors.devices.zapper_iot import DeviceConnector


class ZapperIoTTests(unittest.TestCase):
    """Test Cases for the Zapper IoT class."""

    def test_validate_configuration(self):
        """Test the function creates a proper provision_data
        dictionary when valid data are provided.
        """
        device = DeviceConnector({"control_host": "zapper-host"})
        device.job_data = {
            "provision_data": {
                "preset": "TestPreset",
                "preset_kwargs": {"arg1": "value1"},
                "urls": ["http://test.tar.gz"],
            }
        }

        args, kwargs = device._validate_configuration()

        expected = {
            "username": "ubuntu",
            "password": "ubuntu",
            "preset": "TestPreset",
            "preset_kwargs": {"arg1": "value1"},
            "urls": ["http://test.tar.gz"],
        }

        self.assertEqual(args, ())
        self.assertDictEqual(kwargs, expected)

    def test_validate_configuration_ubuntu_sso_email(self):
        """Test the function username will be ubuntu_sso_email if provided."""
        device = DeviceConnector({"control_host": "zapper-host"})
        device.job_data = {
            "provision_data": {
                "ubuntu_sso_email": "test@example.com",
                "preset": "TestPreset",
                "urls": ["http://test.tar.gz"],
            }
        }

        args, kwargs = device._validate_configuration()

        expected = {
            "username": "test@example.com",
            "password": "ubuntu",
            "preset": "TestPreset",
            "preset_kwargs": None,
            "urls": ["http://test.tar.gz"],
        }

        self.assertEqual(args, ())
        self.assertDictEqual(kwargs, expected)

    def test_validate_configuration_provision_plan(self):
        """Test the function validates a custom test plan
        when provided.
        """
        device = DeviceConnector({"control_host": "zapper-host"})
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
            "preset": None,
            "preset_kwargs": None,
        }
        self.maxDiff = None
        self.assertEqual(args, ())
        self.assertDictEqual(expected, kwargs)

    def test_validate_configuration_ubuntu_sso_email_provision_plan(
        self
    ):
        """Test the function validates a custom test plan
        when provided and an ubuntu_sso_email is provided.
        The username should be overridden with the ubuntu_sso_email.
        """
        device = DeviceConnector({"control_host": "zapper-host"})
        device.job_data = {
            "provision_data": {
                "ubuntu_sso_email": "test@example.com",
                "provision_plan": {
                    "config": {
                        "project_name": "name",
                        "serial_console": {
                            "port": "/dev/ttySanity1",
                            "baud_rate": 115200,
                        },
                        "network": "eth0",
                    },
                    "run_stage": [
                        {"initial_login": {"method": "console-conf"}},
                    ],
                },
            }
        }

        args, kwargs = device._validate_configuration()

        expected = {
            "username": "test@example.com",
            "password": "ubuntu",
            "custom_provision_plan": {
                "config": {
                    "project_name": "name",
                    "username": "test@example.com",  # this gets overridden
                    "password": "ubuntu",
                    "serial_console": {
                        "port": "/dev/ttySanity1",
                        "baud_rate": 115200,
                    },
                    "network": "eth0",
                },
                "run_stage": [
                    {"initial_login": {"method": "console-conf"}},
                ],
            },
            "urls": [],
            "preset": None,
            "preset_kwargs": None,
        }
        self.maxDiff = None
        self.assertEqual(args, ())
        self.assertDictEqual(expected, kwargs)

    def test_validate_configuration_ubuntu_sso_email_missing_provision_plan(
        self
    ):
        """Test the function raises an exception if ubuntu_sso_email is not
        provided and the initial login method is console-conf.
        """
        fake_config = {
            "device_ip": "1.1.1.1",
            "control_host": "zapper-host",
            "reboot_script": ["cmd1", "cmd2"],
        }
        device = DeviceConnector(fake_config)
        device.job_data = {
            "provision_data": {
                "provision_plan": {
                    "config": {
                        "project_name": "name",
                        "serial_console": {
                            "port": "/dev/ttySanity1",
                            "baud_rate": 115200,
                        },
                        "network": "eth0",
                    },
                    "run_stage": [
                        {"initial_login": {"method": "console-conf"}},
                    ],
                }
            }
        }

        with self.assertRaises(ProvisioningError):
            device._validate_configuration()

    def test_validate_configuration_invalid_url(self):
        """Test the function raises an exception if one of
        the url is not valid.
        """
        fake_config = {
            "device_ip": "1.1.1.1",
            "control_host": "zapper-host",
            "reboot_script": ["cmd1", "cmd2"],
        }
        device = DeviceConnector(fake_config)
        device.job_data = {
            "provision_data": {
                "urls": ["not-a-url"],
            }
        }

        with self.assertRaises(ProvisioningError):
            device._validate_configuration()

    def test_validate_configuration_invalid_provision_plan_key_error(
        self
    ):
        """Test the function raises an exception if the
        provided custom testplan is not valid.
        """
        fake_config = {
            "device_ip": "1.1.1.1",
            "control_host": "zapper-host",
            "reboot_script": ["cmd1", "cmd2"],
        }
        device = DeviceConnector(fake_config)
        device.job_data = {
            "provision_data": {"provision_plan": {"key1": "value1"}}
        }

        with self.assertRaises(ProvisioningError):
            device._validate_configuration()

    def test_validate_configuration_invalid_provision_plan_value_error(
        self
    ):
        """Test the function raises an exception if the
        provided custom testplan is not valid.
        """
        fake_config = {
            "device_ip": "1.1.1.1",
            "control_host": "zapper-host",
            "reboot_script": ["cmd1", "cmd2"],
        }
        device = DeviceConnector(fake_config)
        device.job_data = {
            "provision_data": {
                "provision_plan": {
                    "config": {"key1": "value1"},
                }
            }
        }
        device.config = {
            "device_ip": "",
            "reboot_script": [],
        }

        with self.assertRaises(ProvisioningError):
            device._validate_configuration()

    @patch.object(DeviceConnector, "_copy_ssh_id")
    def test_post_run_actions_copy_ssh_id_no_provision_plan(
        self, mock_copy_ssh_id
    ):
        """Test the function copy the ssh id if there is no provision plan
        and without ubuntu_sso_email.
        """
        fake_config = {"device_ip": "1.1.1.1", "control_host": "zapper-host"}
        device = DeviceConnector(fake_config)
        device.job_data = {"provision_data": {}}
        device._post_run_actions(args=None)
        mock_copy_ssh_id.assert_called_once()

    @patch.object(DeviceConnector, "_copy_ssh_id")
    def test_post_run_actions_not_copy_ssh_id_ubuntu_sso_email(
        self, mock_copy_ssh_id
    ):
        """Test the function does not copy the ssh id if there is
        buntu_sso_email.
        """
        fake_config = {"device_ip": "1.1.1.1", "control_host": "zapper-host"}
        device = DeviceConnector(fake_config)
        device.job_data = {
            "provision_data": {
                "ubuntu_sso_email": "test@example.com",
            }
        }
        device._post_run_actions(args=None)
        mock_copy_ssh_id.assert_not_called()

    @patch.object(DeviceConnector, "_copy_ssh_id")
    def test_post_run_actions_copy_ssh_id_provision_plan(
        self, mock_copy_ssh_id
    ):
        """Test the function copies the ssh id if the
        initial login method is Not console-conf.
        """
        fake_config = {"device_ip": "1.1.1.1", "control_host": "zapper-host"}
        device = DeviceConnector(fake_config)
        device.job_data = {
            "provision_data": {
                "provision_plan": {
                    "run_stage": [{"initial_login": {"method": "system-user"}}]
                }
            }
        }
        device._post_run_actions(args=None)

        mock_copy_ssh_id.assert_called_once()


if __name__ == "__main__":
    unittest.main()
