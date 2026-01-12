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
        fake_config = {"device_ip": "1.1.1.1"}
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
        fake_config = {"device_ip": "1.1.1.1"}
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
        """Test __check_rpyc_server_on_host succeeds when port is open."""
        fake_config = {"device_ip": "1.1.1.1", "agent_name": "test-agent"}
        connector = MockConnector(fake_config)

        mock_subprocess = mocker.patch("subprocess.run")

        # Access the private method
        connector._ZapperConnector__check_rpyc_server_on_host("test-host")

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
        """Test connection check raises ConnectionError on failure."""
        fake_config = {"device_ip": "1.1.1.1", "agent_name": "test-agent"}
        connector = MockConnector(fake_config)

        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "nc"),
        )

        with pytest.raises(ConnectionError):
            connector._ZapperConnector__check_rpyc_server_on_host("test-host")

    def test_init_waits_for_rpyc_when_control_host_configured(self, mocker):
        """Test __init__ calls wait_online when control_host is in config."""
        mock_wait_online = mocker.patch.object(ZapperConnector, "wait_online")

        fake_config = {
            "device_ip": "1.1.1.1",
            "agent_name": "test-agent",
            "control_host": "zapper-host",
        }
        MockConnector(fake_config)

        mock_wait_online.assert_called_once()
        call_args = mock_wait_online.call_args
        assert call_args[0][1] == "zapper-host"
        assert call_args[0][2] == 60

    def test_init_skips_wait_when_no_control_host(self, mocker):
        """Test __init__ does not call wait_online without control_host."""
        mock_wait_online = mocker.patch.object(ZapperConnector, "wait_online")

        fake_config = {"device_ip": "1.1.1.1", "agent_name": "test-agent"}
        MockConnector(fake_config)

        mock_wait_online.assert_not_called()
