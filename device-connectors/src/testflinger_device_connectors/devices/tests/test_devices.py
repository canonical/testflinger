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

import subprocess
import unittest
from unittest.mock import Mock, call, patch

from testflinger_device_connectors.devices import DefaultDevice


class DefaultDeviceTests(unittest.TestCase):
    """Unit tests for DefaultDevice class."""

    @patch("subprocess.check_call")
    def test_copy_ssh_id(self, mock_check):
        """Test whether the function copies the agent's SSH key
        to the DUT.
        """
        connector = DefaultDevice()
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
        connector = DefaultDevice()
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
        connector = DefaultDevice()
        connector = DefaultDevice()

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
