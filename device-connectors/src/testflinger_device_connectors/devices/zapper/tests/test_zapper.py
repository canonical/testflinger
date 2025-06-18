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

import unittest
from unittest.mock import Mock, patch

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

        fake_config = {"device_ip": "1.1.1.1"}
        connector = MockConnector(fake_config)
        connector._run("localhost", *args, **kwargs)

        api = mock_connect.return_value.root.provision
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
