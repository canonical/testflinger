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
"""Unit tests for Zapper base device connector."""

import subprocess
import unittest
from unittest.mock import Mock, patch

import pytest
import requests

from testflinger_device_connectors.devices import ProvisioningError
from testflinger_device_connectors.devices.zapper import (
    ZapperConnector,
    logger,
)


class MockConnector(ZapperConnector):
    PROVISION_METHOD = "Test"

    def _validate_configuration(self):
        return (), {}

    def _post_run_actions(self, args):
        pass


class ZapperConnectorTests(unittest.TestCase):
    """Unit tests for ZapperConnector class."""

    @patch("rpyc.connect")
    def test_run(self, mock_connect):
        """Test the `run` function connects to a Zapper via RPyC
        and runs the `provision` API.
        """
        args = (1, 2, 3)
        kwargs = {"key1": 1, "key2": 2}

        fake_config = {
            "device_ip": "1.1.1.1",
            "agent_name": "my-agent",
            "control_host": "zapper-host",
            "reboot_script": ["cmd1", "cmd2"],
            "env": {"CID": "202507-01234"},
        }
        connector = MockConnector(fake_config)
        connector._run("localhost", *args, **kwargs)

        api = mock_connect.return_value.root.provision

        kwargs["device_ip"] = "1.1.1.1"
        kwargs["agent_name"] = "my-agent"
        kwargs["reboot_script"] = ["cmd1", "cmd2"]
        kwargs["cid"] = "202507-01234"

        api.assert_called_with(
            MockConnector.PROVISION_METHOD,
            *args,
            logger=logger,
            **kwargs,
        )

    def test_copy_ssh_id(self):
        """Test the function collects the device info from
        job and config and attempts to copy the agent SSH
        key to the DUT.
        """
        fake_config = {"device_ip": "1.1.1.1", "control_host": "zapper-host"}
        connector = MockConnector(fake_config)
        connector.job_data = {
            "test_data": {
                "test_username": "myuser",
                "test_password": "mypassword",
            }
        }
        connector.config = {"device_ip": "192.168.1.2"}

        connector.copy_ssh_key = Mock()
        connector._copy_ssh_id()

        connector.copy_ssh_key.assert_called_once_with(
            "192.168.1.2", "myuser", "mypassword"
        )

    def test_copy_ssh_id_raises(self):
        """Test the function raises a ProvisioningError exception
        in case of failure.
        """
        fake_config = {"device_ip": "1.1.1.1", "control_host": "zapper-host"}
        connector = MockConnector(fake_config)
        connector.job_data = {
            "test_data": {
                "test_username": "myuser",
                "test_password": "mypassword",
            }
        }
        connector.config = {"device_ip": "192.168.1.2"}

        connector.copy_ssh_key = Mock()
        connector.copy_ssh_key.side_effect = RuntimeError
        with self.assertRaises(ProvisioningError):
            connector._copy_ssh_id()


class TestZapperConnectorRpycCheck:
    """Tests for ZapperConnector RPyC server check."""

    def test_check_rpyc_server_on_host_success(self, mocker):
        """Test _check_rpyc_server_on_host succeeds when port is open."""
        mock_subprocess = mocker.patch("subprocess.run")

        ZapperConnector._check_rpyc_server_on_host("test-host")

        mock_subprocess.assert_called_once()
        call_args = mock_subprocess.call_args
        assert call_args[0][0] == [
            "/usr/bin/nc",
            "-z",
            "-w",
            "3",
            "test-host",
            "60000",
        ]

    def test_check_rpyc_server_on_host_raises_connection_error(self, mocker):
        """Test the function raises ConnectionError on failure."""
        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "nc"),
        )

        with pytest.raises(ConnectionError):
            ZapperConnector._check_rpyc_server_on_host("test-host")

    def test_wait_ready_success(self, mocker):
        """Test wait_ready calls wait_online with correct parameters."""
        from testflinger_device_connectors.devices import DefaultDevice

        mock_wait_online = mocker.patch.object(DefaultDevice, "wait_online")

        ZapperConnector.wait_ready("zapper-host", timeout=30)

        mock_wait_online.assert_called_once_with(
            ZapperConnector._check_rpyc_server_on_host, "zapper-host", 30
        )

    def test_wait_ready_timeout(self, mocker):
        """Test wait_ready raises TimeoutError when server unavailable."""
        from testflinger_device_connectors.devices import DefaultDevice

        mocker.patch.object(
            DefaultDevice, "wait_online", side_effect=TimeoutError
        )

        with pytest.raises(TimeoutError):
            ZapperConnector.wait_ready("zapper-host")


class TestZapperConnectorTypecmux:
    """Tests for ZapperConnector typecmux operations."""

    def test_typecmux_set_state_success(self, mocker):
        """Test typecmux_set_state connects and calls the remote method."""
        mock_connect = mocker.patch("rpyc.connect")
        mock_connection = Mock()
        mock_connect.return_value = mock_connection

        ZapperConnector.typecmux_set_state("zapper-host", "OFF")

        mock_connect.assert_called_once_with(
            "zapper-host",
            60000,
            config={
                "allow_public_attrs": True,
                "sync_request_timeout": 60,
            },
        )
        mock_connection.root.typecmux_set_state.assert_called_once_with(
            alias="default", state="OFF"
        )

    def test_typecmux_set_state_with_dut(self, mocker):
        """Test typecmux_set_state with DUT state."""
        mock_connect = mocker.patch("rpyc.connect")
        mock_connection = Mock()
        mock_connect.return_value = mock_connection

        ZapperConnector.typecmux_set_state("zapper-host", "DUT")

        mock_connection.root.typecmux_set_state.assert_called_once_with(
            alias="default", state="DUT"
        )


class TestZapperConnectorDisconnectUsbStick:
    """Tests for ZapperConnector USB stick disconnect functionality."""

    def test_disconnect_usb_stick_success(self, mocker):
        """Test disconnect_usb_stick succeeds when Zapper is available."""
        config = {"control_host": "zapper-host", "device_ip": "1.2.3.4"}

        mock_wait_ready = mocker.patch.object(ZapperConnector, "wait_ready")
        mock_typecmux = mocker.patch.object(
            ZapperConnector, "typecmux_set_state"
        )

        ZapperConnector.disconnect_usb_stick(config)

        mock_wait_ready.assert_called_once_with("zapper-host")
        mock_typecmux.assert_called_once_with("zapper-host", "OFF")

    def test_disconnect_usb_stick_no_control_host(self, mocker):
        """Test disconnect_usb_stick skips when no control_host."""
        config = {"device_ip": "1.2.3.4"}

        mock_wait_ready = mocker.patch.object(ZapperConnector, "wait_ready")
        mock_typecmux = mocker.patch.object(
            ZapperConnector, "typecmux_set_state"
        )

        ZapperConnector.disconnect_usb_stick(config)

        mock_wait_ready.assert_not_called()
        mock_typecmux.assert_not_called()

    def test_disconnect_usb_stick_timeout_non_blocking(self, mocker):
        """Test disconnect_usb_stick handles timeout gracefully."""
        config = {"control_host": "zapper-host", "device_ip": "1.2.3.4"}

        mocker.patch.object(
            ZapperConnector, "wait_ready", side_effect=TimeoutError
        )
        mock_typecmux = mocker.patch.object(
            ZapperConnector, "typecmux_set_state"
        )

        # Should not raise
        ZapperConnector.disconnect_usb_stick(config)

        mock_typecmux.assert_not_called()

    def test_disconnect_usb_stick_connection_error_non_blocking(self, mocker):
        """Test disconnect_usb_stick handles connection error gracefully."""
        config = {"control_host": "zapper-host", "device_ip": "1.2.3.4"}

        mocker.patch.object(
            ZapperConnector, "wait_ready", side_effect=ConnectionError
        )
        mock_typecmux = mocker.patch.object(
            ZapperConnector, "typecmux_set_state"
        )

        # Should not raise
        ZapperConnector.disconnect_usb_stick(config)

        mock_typecmux.assert_not_called()


class TestZapperConnectorRestApi:
    """Tests for ZapperConnector REST API client."""

    def test_api_post(self, mocker):
        """Test _api_post sends a POST request to the correct URL."""
        mock_post = mocker.patch("requests.post")
        mock_post.return_value.raise_for_status = Mock()

        connector = MockConnector({"control_host": "zapper-host"})
        connector._api_post("/api/v1/system/poweroff", timeout=10)

        mock_post.assert_called_once_with(
            "http://zapper-host:8000/api/v1/system/poweroff",
            timeout=10,
        )
        mock_post.return_value.raise_for_status.assert_called_once()

    def test_api_post_raises_on_http_error(self, mocker):
        """Test _api_post raises on HTTP error status."""
        mock_post = mocker.patch("requests.post")
        mock_post.return_value.raise_for_status.side_effect = (
            requests.HTTPError
        )

        connector = MockConnector({"control_host": "zapper-host"})
        with pytest.raises(requests.HTTPError):
            connector._api_post("/api/v1/system/poweroff")
