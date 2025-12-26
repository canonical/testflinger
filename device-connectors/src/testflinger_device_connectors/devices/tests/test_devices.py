# Copyright (C) 2025 Canonical
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
"""Unit tests for DefaultDevice base device connector."""

import json
import subprocess
import unittest
from unittest.mock import Mock, call, patch

from testflinger_device_connectors.devices import (
    DefaultDevice,
    copy_ssh_key,
    copy_ssh_keys_to_devices,
)


class DefaultDeviceTests(unittest.TestCase):
    """Unit tests for DefaultDevice class."""

    @patch("subprocess.check_call")
    def test_copy_ssh_id(self, mock_check):
        """Test whether the function copies the agent's SSH key
        to the DUT.
        """
        fake_config = {"device_ip": "10.10.10.10", "agent_name": "fake_agent"}
        DefaultDevice(fake_config)
        copy_ssh_key(
            "192.168.1.2",
            "username",
            "password",
        )

        cmd = (
            "sshpass -p password ssh-copy-id -f"
            + " -o StrictHostKeyChecking=no"
            + " -o UserKnownHostsFile=/dev/null username@192.168.1.2"
        )
        mock_check.assert_called_once_with(cmd.split(), timeout=30)

    @patch("subprocess.check_call")
    def test_copy_ssh_id_with_key(self, mock_check):
        """Test whether the function copies the provided key
        to the DUT.
        """
        fake_config = {"device_ip": "10.10.10.10", "agent_name": "fake_agent"}
        DefaultDevice(fake_config)
        copy_ssh_key(
            "192.168.1.2",
            "username",
            key="key.pub",
        )

        cmd = (
            "ssh-copy-id -f"
            + " -i key.pub"
            + " -o StrictHostKeyChecking=no"
            + " -o UserKnownHostsFile=/dev/null username@192.168.1.2"
        )
        mock_check.assert_called_once_with(cmd.split(), timeout=30)

    @patch("time.sleep", Mock())
    @patch("subprocess.check_call")
    def test_copy_ssh_id_raises(self, mock_check):
        """Test whether the function raises a RuntimeError
        exception after 3 failed attempts.
        """
        fake_config = {"device_ip": "10.10.10.10", "agent_name": "fake_agent"}
        DefaultDevice(fake_config)

        mock_check.side_effect = subprocess.CalledProcessError(1, "")

        with self.assertRaises(RuntimeError):
            copy_ssh_key(
                "192.168.1.2",
                "username",
                "password",
            )

        cmd = (
            "sshpass -p password ssh-copy-id -f"
            + " -o StrictHostKeyChecking=no"
            + " -o UserKnownHostsFile=/dev/null username@192.168.1.2"
        )
        expected = call(cmd.split(), timeout=30)
        mock_check.assert_has_calls(10 * [expected])

    def test_write_device_info(self):
        """Validate device-info file can be read upon class initialization."""
        fake_config = {"device_ip": "10.10.10.10", "agent_name": "fake_agent"}
        DefaultDevice(fake_config)

        with open("device-info.json") as devinfo_file:
            device_info = json.load(devinfo_file)["device_info"]

        # Compare retrieved data with expected data
        assert all(
            device_info[key] == value for key, value in fake_config.items()
        )


class CopySshKeysToDevicesTests(unittest.TestCase):
    """Unit tests for copy_ssh_keys_to_devices function."""

    @patch("testflinger_device_connectors.devices.copy_ssh_key")
    @patch("testflinger_device_connectors.devices.import_ssh_key")
    @patch("os.unlink")
    def test_copy_ssh_keys_to_devices_success(
        self, mock_unlink, mock_import, mock_copy
    ):
        """Test successful copying of SSH keys to multiple devices."""
        ssh_keys = ["key1", "key2"]
        device_ips = ["192.168.1.1", "192.168.1.2"]

        copy_ssh_keys_to_devices(ssh_keys, device_ips, "testuser")

        # Should unlink key.pub twice (once per key)
        assert mock_unlink.call_count == 2
        mock_unlink.assert_has_calls([call("key.pub"), call("key.pub")])

        # Should import each key
        mock_import.assert_has_calls(
            [call("key1", keyfile="key.pub"), call("key2", keyfile="key.pub")]
        )

        # Should copy each key to each device (2 keys * 2 devices = 4 calls)
        expected_copy_calls = [
            call("192.168.1.1", "testuser", key="key.pub"),
            call("192.168.1.2", "testuser", key="key.pub"),
            call("192.168.1.1", "testuser", key="key.pub"),
            call("192.168.1.2", "testuser", key="key.pub"),
        ]
        mock_copy.assert_has_calls(expected_copy_calls)

    @patch("testflinger_device_connectors.devices.copy_ssh_key")
    @patch("testflinger_device_connectors.devices.import_ssh_key")
    @patch("os.unlink")
    def test_copy_ssh_keys_to_devices_import_failure(
        self, mock_unlink, mock_import, mock_copy
    ):
        """Test handling of import_ssh_key failure."""
        ssh_keys = ["key1"]
        device_ips = ["192.168.1.1"]

        # Make import_ssh_key raise RuntimeError
        mock_import.side_effect = RuntimeError("Import failed")

        copy_ssh_keys_to_devices(ssh_keys, device_ips, "testuser")

        # Should still attempt to unlink
        mock_unlink.assert_called_once_with("key.pub")

        # Should attempt to import
        mock_import.assert_called_once_with("key1", keyfile="key.pub")

        # Should not attempt to copy since import failed
        mock_copy.assert_not_called()

    @patch("testflinger_device_connectors.devices.copy_ssh_key")
    @patch("testflinger_device_connectors.devices.import_ssh_key")
    @patch("os.unlink")
    def test_copy_ssh_keys_to_devices_copy_failure(
        self, mock_unlink, mock_import, mock_copy
    ):
        """Test handling of copy_ssh_key failure."""
        ssh_keys = ["key1"]
        device_ips = ["192.168.1.1"]

        # Make copy_ssh_key raise RuntimeError
        mock_copy.side_effect = RuntimeError("Copy failed")

        copy_ssh_keys_to_devices(ssh_keys, device_ips, "testuser")

        # Should unlink and import successfully
        mock_unlink.assert_called_once_with("key.pub")
        mock_import.assert_called_once_with("key1", keyfile="key.pub")

        # Should attempt to copy but fail gracefully
        mock_copy.assert_called_once_with(
            "192.168.1.1", "testuser", key="key.pub"
        )

    @patch("testflinger_device_connectors.devices.copy_ssh_key")
    @patch("testflinger_device_connectors.devices.import_ssh_key")
    @patch("os.unlink", side_effect=FileNotFoundError)
    def test_copy_ssh_keys_to_devices_file_not_found(
        self, mock_unlink, mock_import, mock_copy
    ):
        """Test handling when key.pub file doesn't exist."""
        ssh_keys = ["key1"]
        device_ips = ["192.168.1.1"]

        copy_ssh_keys_to_devices(ssh_keys, device_ips, "testuser")

        # Should attempt to unlink but suppress FileNotFoundError
        mock_unlink.assert_called_once_with("key.pub")

        # Should continue with import and copy
        mock_import.assert_called_once_with("key1", keyfile="key.pub")
        mock_copy.assert_called_once_with(
            "192.168.1.1", "testuser", key="key.pub"
        )

    @patch("testflinger_device_connectors.devices.copy_ssh_key")
    @patch("testflinger_device_connectors.devices.import_ssh_key")
    @patch("os.unlink")
    def test_copy_ssh_keys_to_devices_empty_lists(
        self, mock_unlink, mock_import, mock_copy
    ):
        """Test with empty SSH keys and device lists."""
        copy_ssh_keys_to_devices([], [])

        # Should not call any functions
        mock_unlink.assert_not_called()
        mock_import.assert_not_called()
        mock_copy.assert_not_called()


class DefaultDeviceReserveTests(unittest.TestCase):
    """Unit tests for DefaultDevice.reserve method."""

    @patch("testflinger_device_connectors.devices.copy_ssh_keys_to_devices")
    @patch("time.sleep")
    def test_reserve_with_ssh_keys(self, mock_sleep, mock_copy_keys):
        """Test DefaultDevice.reserve method with SSH keys."""
        config_data = {"device_ip": "192.168.1.10", "agent_name": "test_agent"}

        job_data = {
            "reserve_data": {"ssh_keys": ["key1", "key2"], "timeout": "1800"},
            "test_data": {"test_username": "testuser"},
        }

        # Create a mock args object
        mock_args = Mock()
        mock_args.config = "test_config.yaml"

        # Mock file operations
        with (
            patch(
                "testflinger_device_connectors.get_test_opportunity",
                return_value=job_data,
            ),
            patch("builtins.open") as mock_open,
        ):
            # Mock the config file read
            mock_open.return_value.__enter__.return_value = Mock()
            mock_open.return_value.__enter__.return_value.read.return_value = (
                '{"device_ip": "192.168.1.10"}'
            )

            with (
                patch(
                    "yaml.safe_load",
                    return_value={"device_ip": "192.168.1.10"},
                ),
                patch("builtins.print"),
            ):
                device = DefaultDevice(config_data)
                device.reserve(mock_args)

        # Verify copy_ssh_keys_to_devices was called with correct parameters
        mock_copy_keys.assert_called_once_with(
            ["key1", "key2"], ["192.168.1.10"], "testuser"
        )

        # Verify sleep was called with timeout
        mock_sleep.assert_called_once_with(1800)

    @patch("testflinger_device_connectors.devices.copy_ssh_keys_to_devices")
    @patch("time.sleep")
    def test_reserve_no_ssh_keys(self, mock_sleep, mock_copy_keys):
        """Test DefaultDevice.reserve method with no SSH keys."""
        config_data = {"device_ip": "192.168.1.10", "agent_name": "test_agent"}

        job_data = {
            "reserve_data": {
                "timeout": "3600"
                # No ssh_keys provided
            },
            "test_data": {"test_username": "testuser"},
        }

        mock_args = Mock()
        mock_args.config = "test_config.yaml"

        with (
            patch(
                "testflinger_device_connectors.get_test_opportunity",
                return_value=job_data,
            ),
            patch("builtins.open") as mock_open,
        ):
            # Mock the config file read
            mock_open.return_value.__enter__.return_value = Mock()
            mock_open.return_value.__enter__.return_value.read.return_value = (
                '{"device_ip": "192.168.1.10"}'
            )

            with (
                patch(
                    "yaml.safe_load",
                    return_value={"device_ip": "192.168.1.10"},
                ),
                patch("builtins.print"),
            ):
                device = DefaultDevice(config_data)
                device.reserve(mock_args)

        # Verify copy_ssh_keys_to_devices was called with empty list
        mock_copy_keys.assert_called_once_with(
            [], ["192.168.1.10"], "testuser"
        )

        # Verify sleep was called with timeout
        mock_sleep.assert_called_once_with(3600)

    @patch("testflinger_device_connectors.devices.copy_ssh_keys_to_devices")
    @patch("time.sleep")
    def test_reserve_default_timeout(self, mock_sleep, mock_copy_keys):
        """Test DefaultDevice.reserve method with default timeout."""
        config_data = {"device_ip": "192.168.1.10", "agent_name": "test_agent"}

        job_data = {
            "reserve_data": {
                "ssh_keys": ["key1"]
                # No timeout provided - should default to 3600
            },
            "test_data": {"test_username": "testuser"},
        }

        mock_args = Mock()
        mock_args.config = "test_config.yaml"

        with (
            patch(
                "testflinger_device_connectors.get_test_opportunity",
                return_value=job_data,
            ),
            patch("builtins.open") as mock_open,
        ):
            # Mock the config file read
            mock_open.return_value.__enter__.return_value = Mock()
            mock_open.return_value.__enter__.return_value.read.return_value = (
                '{"device_ip": "192.168.1.10"}'
            )

            with (
                patch(
                    "yaml.safe_load",
                    return_value={"device_ip": "192.168.1.10"},
                ),
                patch("builtins.print"),
            ):
                device = DefaultDevice(config_data)
                device.reserve(mock_args)

        # Verify copy_ssh_keys_to_devices was called
        mock_copy_keys.assert_called_once_with(
            ["key1"], ["192.168.1.10"], "testuser"
        )

        # Verify sleep was called with default timeout of 3600
        mock_sleep.assert_called_once_with(3600)
