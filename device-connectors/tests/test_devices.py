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
import time
from importlib import import_module
from itertools import product
from unittest.mock import MagicMock, Mock

import pytest
import requests

from testflinger_device_connectors.cmd import STAGES
from testflinger_device_connectors.devices import (
    DEVICE_CONNECTORS,
    DefaultControlHost,
    DefaultDevice,
    get_device_stage_func,
)

STAGES_CONNECTORS_PRODUCT = tuple(product(STAGES, DEVICE_CONNECTORS))


@pytest.mark.parametrize("stage,device", STAGES_CONNECTORS_PRODUCT)
def test_get_device_stage_func(stage, device):
    """Check that we can load all stages from all device connectors."""
    fake_config = {"device_ip": "10.10.10.10", "agent_name": "fake_agent"}

    # Zapper connectors require control_host
    if device.startswith("zapper"):
        fake_config["control_host"] = "fake-zapper-host"

    connector_instance = import_module(
        f"testflinger_device_connectors.devices.{device}"
    ).DeviceConnector(config=fake_config)
    orig_func = getattr(connector_instance, stage)
    func = get_device_stage_func(device, stage, fake_config)
    assert func.__func__ is orig_func.__func__


class TestWaitOnline:
    """Tests for DefaultControlHost.wait_online method."""

    def test_wait_online_succeeds_immediately(self, mocker):
        """Test wait_online succeeds when check passes on first try."""
        mocker.patch("time.sleep")
        mock_check = MagicMock()

        DefaultControlHost("test-host").wait_online(mock_check, 60)

        mock_check.assert_called_once_with()

    def test_wait_online_retries_then_succeeds(self, mocker):
        """Test wait_online retries when check fails then succeeds."""
        mocker.patch("time.sleep")
        mock_check = MagicMock(
            side_effect=[ConnectionError, ConnectionError, None]
        )

        DefaultControlHost("test-host").wait_online(mock_check, 60)

        assert mock_check.call_count == 3

    def test_wait_online_times_out(self, mocker):
        """Test wait_online raises TimeoutError when timeout is reached."""
        mocker.patch("time.sleep")
        mocker.patch("time.time", side_effect=[0, 1, 2, 100])
        mock_check = MagicMock(side_effect=ConnectionError)

        with pytest.raises(TimeoutError):
            DefaultControlHost("test-host").wait_online(mock_check, 10)


class TestCheckSshServerOnHost:
    """Tests for DefaultControlHost._check_ssh method."""

    def test_check_ssh_server_success(self, mocker):
        """Test SSH check succeeds when nc command succeeds."""
        mock_subprocess = mocker.patch("subprocess.run")

        DefaultControlHost("test-host")._check_ssh()

        mock_subprocess.assert_called_once_with(
            ["/usr/bin/nc", "-z", "-w", "3", "test-host", "22"],
            check=True,
            capture_output=True,
            text=True,
        )

    def test_check_ssh_server_raises_connection_error(self, mocker):
        """Test SSH check raises ConnectionError when nc fails."""
        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "nc"),
        )

        with pytest.raises(ConnectionError):
            DefaultControlHost("test-host")._check_ssh()


class TestCheckPing:
    """Tests for DefaultControlHost._check_ping method."""

    def test_check_ping_success(self, mocker):
        """Test ping check succeeds when host responds."""
        mock_subprocess = mocker.patch("subprocess.run")

        DefaultControlHost("test-host")._check_ping()

        mock_subprocess.assert_called_once_with(
            ["/usr/bin/ping", "-c", "1", "-W", "3", "test-host"],
            check=True,
            capture_output=True,
        )

    def test_check_ping_raises_connection_error(self, mocker):
        """Test ping check raises ConnectionError when unreachable."""
        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "ping"),
        )

        with pytest.raises(ConnectionError):
            DefaultControlHost("test-host")._check_ping()


class TestRebootControlHost:
    """Tests for DefaultControlHost.reboot method."""

    def test_reboot_control_host_success(self, mocker):
        """Test reboot runs script commands successfully."""
        mock_subprocess = mocker.patch("subprocess.run")

        DefaultControlHost("host", ["cmd1", "cmd2"]).reboot()

        assert mock_subprocess.call_count == 2

    def test_reboot_control_host_called_process_error(self, mocker):
        """Test reboot handles CalledProcessError gracefully."""
        error = subprocess.CalledProcessError(1, "cmd1")
        error.stdout = "some stdout"
        error.stderr = "some stderr"
        mocker.patch("subprocess.run", side_effect=error)

        # Should not raise
        DefaultControlHost("host", ["cmd1"]).reboot()

    def test_reboot_control_host_timeout_expired(self, mocker):
        """Test reboot handles TimeoutExpired gracefully."""
        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired("cmd1", 60),
        )

        # Should not raise
        DefaultControlHost("host", ["cmd1"]).reboot()

    def test_reboot_control_host_unexpected_error(self, mocker):
        """Test reboot handles unexpected exceptions gracefully."""
        mocker.patch("subprocess.run", side_effect=OSError("unexpected"))

        # Should not raise
        DefaultControlHost("host", ["cmd1"]).reboot()


class TestPreProvisionHook:
    """Tests for DefaultDevice.pre_provision_hook method."""

    def test_no_control_host(self, mocker):
        """Test hook returns early when no control_host configured."""
        mocker.patch("builtins.open", mocker.mock_open())
        mock_power_cycle = mocker.patch.object(
            DefaultControlHost, "power_cycle"
        )
        device = DefaultDevice({"device_ip": "1.1.1.1"})

        device.pre_provision_hook()

        mock_power_cycle.assert_not_called()

    def test_no_reboot_script(self, mocker):
        """Test hook returns early when no reboot script configured."""
        mocker.patch("builtins.open", mocker.mock_open())
        mock_power_cycle = mocker.patch.object(
            DefaultControlHost, "power_cycle"
        )
        device = DefaultDevice(
            {"device_ip": "1.1.1.1", "control_host": "control-host"}
        )

        device.pre_provision_hook()

        mock_power_cycle.assert_not_called()

    def test_delegates_to_power_cycle(self, mocker):
        """Test hook creates DefaultControlHost and calls power_cycle."""
        mocker.patch("builtins.open", mocker.mock_open())
        mock_power_cycle = mocker.patch.object(
            DefaultControlHost, "power_cycle"
        )
        device = DefaultDevice(
            {
                "device_ip": "1.1.1.1",
                "control_host": "control-host",
                "control_host_reboot_script": ["reboot-cmd"],
            }
        )

        device.pre_provision_hook()

        mock_power_cycle.assert_called_once()


class TestDefaultControlHostPowerCycle:
    """Tests for DefaultControlHost.power_cycle and ssh_fallback."""

    def test_rest_poweroff_path(self, mocker):
        """Test power_cycle powers off via REST, reboots, and waits."""
        _ = mocker.patch.object(time, "sleep")
        mock_post = mocker.patch.object(requests, "post")
        mock_post.return_value.raise_for_status = Mock()
        mock_reboot = mocker.patch.object(DefaultControlHost, "reboot")
        mock_wait_offline = mocker.patch.object(
            DefaultControlHost, "wait_offline"
        )
        mock_wait_ready = mocker.patch.object(DefaultControlHost, "wait_ready")
        host = DefaultControlHost("control-host", ["reboot-cmd"])

        host.power_cycle()

        mock_post.assert_called_once_with(
            "http://control-host:8000/api/v1/system/poweroff", timeout=10
        )
        mock_wait_offline.assert_called_once_with(host._check_ping, 30)
        mock_reboot.assert_called_once()
        mock_wait_ready.assert_called_once_with(timeout=300)

    def test_ssh_fallback_host_already_up(self, mocker):
        """Test ssh_fallback skips reboot when host is reachable."""
        mock_subprocess = mocker.patch("subprocess.run")

        DefaultControlHost("control-host", ["reboot-cmd"]).ssh_fallback()

        # Only the SSH check, no reboot
        mock_subprocess.assert_called_once()

    def test_ssh_fallback_reboots_when_host_down(self, mocker):
        """Test ssh_fallback reboots and waits when host is unreachable."""
        mocker.patch("time.sleep")
        mocker.patch("time.time", side_effect=[0, 1, 2, 3])
        mocker.patch(
            "subprocess.run",
            side_effect=[
                subprocess.CalledProcessError(1, "nc"),  # SSH check fails
                None,  # Reboot script succeeds
                None,  # SSH check in wait_online succeeds
            ],
        )

        DefaultControlHost("control-host", ["reboot-cmd"]).ssh_fallback()

        assert subprocess.run.call_count == 3

    def test_ssh_fallback_handles_timeout(self, mocker):
        """Test ssh_fallback handles timeout gracefully."""
        mocker.patch("time.sleep")
        mocker.patch("time.time", side_effect=[0, 0, 500, 500])
        mocker.patch(
            "subprocess.run",
            side_effect=[
                subprocess.CalledProcessError(1, "nc"),  # SSH check fails
                None,  # Reboot script succeeds
                subprocess.CalledProcessError(1, "nc"),  # wait_online check
            ],
        )

        # Should not raise - timeout is handled gracefully
        DefaultControlHost("control-host", ["reboot-cmd"]).ssh_fallback()

    def test_falls_back_to_ssh_when_rest_unavailable(self, mocker):
        """Test power_cycle falls back to ssh_fallback on RequestException."""
        mocker.patch.object(
            requests, "post", side_effect=requests.ConnectionError
        )
        mock_ssh_fallback = mocker.patch.object(
            DefaultControlHost, "ssh_fallback"
        )

        DefaultControlHost("control-host", ["reboot-cmd"]).power_cycle()

        mock_ssh_fallback.assert_called_once()


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
