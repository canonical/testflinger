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
from unittest.mock import Mock, call, patch

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
        """
        Test the `run` function connects to a Zapper via RPyC
        and runs the `provision` API.
        """

        args = (1, 2, 3)
        kwargs = {"key1": 1, "key2": 2}

        connector = MockConnector()
        connector._run("localhost", *args, **kwargs)

        api = mock_connect.return_value.root.provision
        api.assert_called_with(
            MockConnector.PROVISION_METHOD,
            *args,
            logger=logger,
            **kwargs,
        )

    @patch("subprocess.check_call")
    def test_copy_ssh_id(self, mock_check):
        """
        Test whether the function copies the agent's SSH key
        to the DUT.
        """

        connector = MockConnector()
        connector.config = {"device_ip": "192.168.1.2"}
        connector.job_data = {
            "test_data": {
                "test_username": "username",
                "test_password": "password",
            },
        }
        connector._copy_ssh_id()

        cmd = (
            "sshpass -p password ssh-copy-id"
            + " -o StrictHostKeyChecking=no"
            + " -o UserKnownHostsFile=/dev/null username@192.168.1.2"
        )
        mock_check.assert_called_once_with(cmd.split(), timeout=60)

    @patch("time.sleep", Mock())
    @patch("subprocess.check_call")
    def test_copy_ssh_id_raises(self, mock_check):
        """
        Test whether the function raises a ProvisioningError
        exception after 3 failed attempts.
        """

        connector = MockConnector()
        connector.config = {"device_ip": "192.168.1.2"}
        connector.job_data = {
            "test_data": {
                "test_username": "username",
                "test_password": "password",
            },
        }
        mock_check.side_effect = subprocess.CalledProcessError(1, "")

        with self.assertRaises(ProvisioningError):
            connector._copy_ssh_id()

        cmd = (
            "sshpass -p password ssh-copy-id"
            + " -o StrictHostKeyChecking=no"
            + " -o UserKnownHostsFile=/dev/null username@192.168.1.2"
        )
        expected = call(cmd.split(), timeout=60)
        mock_check.assert_has_calls(3 * [expected])
