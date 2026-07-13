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

import requests

from testflinger_device_connectors.devices import (
    DefaultControlHost,
    DefaultDevice,
)


class DefaultDeviceTests(unittest.TestCase):
    """Unit tests for DefaultDevice class."""

    @patch("subprocess.check_call")
    def test_copy_ssh_id(self, mock_check):
        """Test whether the function copies the agent's SSH key
        to the DUT.
        """
        fake_config = {"device_ip": "10.10.10.10", "agent_name": "fake_agent"}
        connector = DefaultDevice(fake_config)
        connector.copy_ssh_key(
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
        connector = DefaultDevice(fake_config)
        connector.copy_ssh_key(
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
        connector = DefaultDevice(fake_config)

        mock_check.side_effect = subprocess.CalledProcessError(1, "")

        with self.assertRaises(RuntimeError):
            connector.copy_ssh_key(
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

    @patch("time.sleep", Mock())
    @patch("time.time", side_effect=[0, 1, 2, 3])
    def test_wait_online_success(self, _mock_time):
        """Test wait_online returns when the check succeeds."""
        check = Mock(side_effect=[ConnectionError, None])
        DefaultControlHost("host").wait_online(check, 10)
        assert check.call_count == 2

    @patch("time.sleep", Mock())
    @patch("time.time", side_effect=[0, 5, 11])
    def test_wait_online_timeout(self, _mock_time):
        """Test wait_online raises TimeoutError when check never succeeds."""
        check = Mock(side_effect=ConnectionError)
        with self.assertRaises(TimeoutError):
            DefaultControlHost("host").wait_online(check, 10)

    @patch("time.sleep", Mock())
    @patch("time.time", side_effect=[0, 1, 2, 3])
    def test_wait_offline_success(self, _mock_time):
        """Test wait_offline returns when the check starts failing."""
        check = Mock(side_effect=[None, ConnectionError])
        DefaultControlHost("host").wait_offline(check, 10)
        assert check.call_count == 2

    @patch("time.sleep", Mock())
    @patch("time.time", side_effect=[0, 5, 11])
    def test_wait_offline_timeout(self, _mock_time):
        """Test wait_offline raises TimeoutError when host stays online."""
        check = Mock()
        with self.assertRaises(TimeoutError):
            DefaultControlHost("host").wait_offline(check, 10)

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


class DefaultControlHostSetupTests(unittest.TestCase):
    """Unit tests for DefaultControlHost.setup_provisioning."""

    @patch("testflinger_device_connectors.devices.requests.post")
    def test_setup_provisioning_posts_to_endpoint(self, mock_post):
        """setup_provisioning POSTs to the setup/provisioning endpoint."""
        DefaultControlHost("host").setup_provisioning()

        mock_post.assert_called_once_with(
            "http://host:8000/api/v1/system/setup/provisioning",
            timeout=10,
        )
        mock_post.return_value.raise_for_status.assert_called_once_with()

    @patch("testflinger_device_connectors.devices.requests.post")
    def test_setup_provisioning_raises_on_http_error(self, mock_post):
        """setup_provisioning propagates HTTP errors."""
        mock_post.return_value.raise_for_status.side_effect = (
            requests.HTTPError
        )

        with self.assertRaises(requests.HTTPError):
            DefaultControlHost("host").setup_provisioning()


class PreProvisionHookTests(unittest.TestCase):
    """Unit tests for DefaultDevice.pre_provision_hook orchestration."""

    def test_skips_when_no_control_host(self):
        """Nothing runs when no control host is configured."""
        connector = DefaultDevice({"device_ip": "1.2.3.4"})

        with (
            patch.object(connector, "_power_cycle_control_host") as mock_power,
            patch.object(
                connector, "_setup_control_host_provisioning"
            ) as mock_setup,
        ):
            connector.pre_provision_hook()

        mock_power.assert_not_called()
        mock_setup.assert_not_called()

    def test_power_cycles_then_sets_up_provisioning(self):
        """Both steps run, in order, when a control host is configured."""
        connector = DefaultDevice({"control_host": "zapper-host"})

        with (
            patch.object(connector, "_power_cycle_control_host") as mock_power,
            patch.object(
                connector, "_setup_control_host_provisioning"
            ) as mock_setup,
        ):
            connector.pre_provision_hook()

        mock_power.assert_called_once_with("zapper-host")
        mock_setup.assert_called_once_with("zapper-host")

    @patch("testflinger_device_connectors.devices.DefaultControlHost")
    def test_setup_calls_control_host(self, mock_control_host):
        """The setup step asks the control host to set up provisioning."""
        connector = DefaultDevice({"control_host": "zapper-host"})

        connector._setup_control_host_provisioning("zapper-host")

        mock_control_host.assert_called_once_with("zapper-host")
        mock_control_host.return_value.setup_provisioning.assert_called_once_with()

    @patch("testflinger_device_connectors.devices.DefaultControlHost")
    def test_setup_is_best_effort(self, mock_control_host):
        """A failing control host never fails provisioning."""
        mock_control_host.return_value.setup_provisioning.side_effect = (
            RuntimeError
        )
        connector = DefaultDevice({"control_host": "zapper-host"})

        # Should not raise.
        connector._setup_control_host_provisioning("zapper-host")
