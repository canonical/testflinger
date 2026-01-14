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
# along with this program.  If not, see <http://www.gnu.org/licenses/>
"""Tests for the devices module."""

import subprocess
from importlib import import_module
from itertools import product
from unittest.mock import MagicMock

import pytest

from testflinger_device_connectors.cmd import STAGES
from testflinger_device_connectors.devices import (
    DEVICE_CONNECTORS,
    DefaultDevice,
    get_device_stage_func,
)

STAGES_CONNECTORS_PRODUCT = tuple(product(STAGES, DEVICE_CONNECTORS))


@pytest.mark.parametrize("stage,device", STAGES_CONNECTORS_PRODUCT)
def test_get_device_stage_func(stage, device):
    """Check that we can load all stages from all device connectors."""
    fake_config = {"device_ip": "10.10.10.10", "agent_name": "fake_agent"}
    connector_instance = import_module(
        f"testflinger_device_connectors.devices.{device}"
    ).DeviceConnector(config=fake_config)
    orig_func = getattr(connector_instance, stage)
    func = get_device_stage_func(device, stage, fake_config)
    assert func.__func__ is orig_func.__func__


class TestWaitOnline:
    """Tests for DefaultDevice.wait_online static method."""

    def test_wait_online_succeeds_immediately(self, mocker):
        """Test wait_online succeeds when check passes on first try."""
        mocker.patch("time.sleep")
        mock_check = MagicMock()

        DefaultDevice.wait_online(mock_check, "test-host", 60)

        mock_check.assert_called_once_with("test-host")

    def test_wait_online_retries_then_succeeds(self, mocker):
        """Test wait_online retries when check fails then succeeds."""
        mocker.patch("time.sleep")
        mock_check = MagicMock(
            side_effect=[ConnectionError, ConnectionError, None]
        )

        DefaultDevice.wait_online(mock_check, "test-host", 60)

        assert mock_check.call_count == 3

    def test_wait_online_times_out(self, mocker):
        """Test wait_online logs error when timeout is reached."""
        mocker.patch("time.sleep")
        # Simulate time progressing past timeout
        mocker.patch("time.time", side_effect=[0, 1, 2, 100])
        mock_check = MagicMock(side_effect=ConnectionError)
        mock_logger = mocker.patch(
            "testflinger_device_connectors.devices.logger"
        )

        DefaultDevice.wait_online(mock_check, "test-host", 10)

        mock_logger.error.assert_called_once()
        assert "not available" in mock_logger.error.call_args[0][0]


class TestCheckSshServerOnHost:
    """Tests for DefaultDevice.__check_ssh_server_on_host method."""

    def test_check_ssh_server_success(self, mocker):
        """Test SSH check succeeds when nc command succeeds."""
        mocker.patch("builtins.open", mocker.mock_open())
        mock_subprocess = mocker.patch("subprocess.run")
        device = DefaultDevice({"device_ip": "1.1.1.1"})

        # Access the private method
        device._DefaultDevice__check_ssh_server_on_host("test-host")

        mock_subprocess.assert_called_once_with(
            ["/usr/bin/nc", "-z", "-w", "3", "test-host", "22"],
            check=True,
            capture_output=True,
            text=True,
        )

    def test_check_ssh_server_raises_connection_error(self, mocker):
        """Test SSH check raises ConnectionError when nc fails."""
        mocker.patch("builtins.open", mocker.mock_open())
        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "nc"),
        )
        device = DefaultDevice({"device_ip": "1.1.1.1"})

        with pytest.raises(ConnectionError):
            device._DefaultDevice__check_ssh_server_on_host("test-host")


class TestRebootControlHost:
    """Tests for DefaultDevice.__reboot_control_host method."""

    def test_reboot_control_host_no_script(self, mocker):
        """Test reboot logs warning when no script is configured."""
        mocker.patch("builtins.open", mocker.mock_open())
        mock_logger = mocker.patch(
            "testflinger_device_connectors.devices.logger"
        )
        device = DefaultDevice({"device_ip": "1.1.1.1"})

        device._DefaultDevice__reboot_control_host()

        mock_logger.warning.assert_called_once()
        assert "No control_host_reboot_script" in str(
            mock_logger.warning.call_args
        )

    def test_reboot_control_host_success(self, mocker):
        """Test reboot runs script commands successfully."""
        mocker.patch("builtins.open", mocker.mock_open())
        mock_subprocess = mocker.patch("subprocess.run")
        device = DefaultDevice(
            {
                "device_ip": "1.1.1.1",
                "control_host_reboot_script": ["cmd1", "cmd2"],
            }
        )

        device._DefaultDevice__reboot_control_host()

        assert mock_subprocess.call_count == 2

    def test_reboot_control_host_called_process_error(self, mocker):
        """Test reboot handles CalledProcessError gracefully."""
        mocker.patch("builtins.open", mocker.mock_open())
        mock_logger = mocker.patch(
            "testflinger_device_connectors.devices.logger"
        )
        error = subprocess.CalledProcessError(1, "cmd1")
        error.stdout = "some stdout"
        error.stderr = "some stderr"
        mocker.patch("subprocess.run", side_effect=error)
        device = DefaultDevice(
            {
                "device_ip": "1.1.1.1",
                "control_host_reboot_script": ["cmd1"],
            }
        )

        # Should not raise
        device._DefaultDevice__reboot_control_host()

        # Check that errors were logged
        error_calls = list(mock_logger.error.call_args_list)
        assert len(error_calls) >= 1

    def test_reboot_control_host_timeout_expired(self, mocker):
        """Test reboot handles TimeoutExpired gracefully."""
        mocker.patch("builtins.open", mocker.mock_open())
        mock_logger = mocker.patch(
            "testflinger_device_connectors.devices.logger"
        )
        timeout_error = subprocess.TimeoutExpired("cmd1", 300)
        mocker.patch("subprocess.run", side_effect=timeout_error)
        device = DefaultDevice(
            {
                "device_ip": "1.1.1.1",
                "control_host_reboot_script": ["cmd1"],
            }
        )

        # Should not raise
        device._DefaultDevice__reboot_control_host()

        # Check that timeout was logged
        error_calls = [str(c) for c in mock_logger.error.call_args_list]
        assert any("timed out" in c for c in error_calls)

    def test_reboot_control_host_unexpected_error(self, mocker):
        """Test reboot handles unexpected exceptions gracefully."""
        mocker.patch("builtins.open", mocker.mock_open())
        mock_logger = mocker.patch(
            "testflinger_device_connectors.devices.logger"
        )
        mocker.patch("subprocess.run", side_effect=OSError("unexpected"))
        device = DefaultDevice(
            {
                "device_ip": "1.1.1.1",
                "control_host_reboot_script": ["cmd1"],
            }
        )

        # Should not raise
        device._DefaultDevice__reboot_control_host()

        # Check that unexpected error was logged
        error_calls = [str(c) for c in mock_logger.error.call_args_list]
        assert any("Unexpected error" in c for c in error_calls)


class TestPreProvisionHook:
    """Tests for DefaultDevice.pre_provision_hook method."""

    def test_pre_provision_hook_no_control_host(self, mocker):
        """Test hook returns early when no control_host configured."""
        mocker.patch("builtins.open", mocker.mock_open())
        mock_logger = mocker.patch(
            "testflinger_device_connectors.devices.logger"
        )
        device = DefaultDevice({"device_ip": "1.1.1.1"})

        device.pre_provision_hook()

        mock_logger.debug.assert_called()
        assert "No control host" in str(mock_logger.debug.call_args_list[0])

    def test_pre_provision_hook_host_already_up(self, mocker):
        """Test hook returns early when control host is already reachable."""
        mocker.patch("builtins.open", mocker.mock_open())
        mock_subprocess = mocker.patch("subprocess.run")
        mock_logger = mocker.patch(
            "testflinger_device_connectors.devices.logger"
        )
        device = DefaultDevice(
            {"device_ip": "1.1.1.1", "control_host": "control-host"}
        )

        device.pre_provision_hook()

        # SSH check was called
        mock_subprocess.assert_called_once()
        # Should log that host is up
        debug_calls = [str(c) for c in mock_logger.debug.call_args_list]
        assert any("already up" in c for c in debug_calls)

    def test_pre_provision_hook_reboots_and_waits(self, mocker):
        """Test hook reboots host and waits when not reachable."""
        mocker.patch("builtins.open", mocker.mock_open())
        mocker.patch("time.sleep")
        mocker.patch("time.time", side_effect=[0, 1, 2, 3])
        # First call fails (host down), subsequent calls succeed
        mocker.patch(
            "subprocess.run",
            side_effect=[
                subprocess.CalledProcessError(1, "nc"),  # SSH check fails
                None,  # Reboot script succeeds
                None,  # SSH check in wait_online succeeds
            ],
        )
        device = DefaultDevice(
            {
                "device_ip": "1.1.1.1",
                "control_host": "control-host",
                "control_host_reboot_script": ["reboot-cmd"],
            }
        )

        device.pre_provision_hook()

        # Verify subprocess was called multiple times
        assert subprocess.run.call_count == 3


class TestProvision:
    """Tests for DefaultDevice.provision method."""

    def test_provision_calls_pre_provision_hook(self, mocker):
        """Test provision method calls pre_provision_hook."""
        mocker.patch("builtins.open", mocker.mock_open())
        mock_hook = mocker.patch.object(DefaultDevice, "pre_provision_hook")
        device = DefaultDevice({"device_ip": "1.1.1.1"})
        mock_args = MagicMock()

        device.provision(mock_args)

        mock_hook.assert_called_once()
