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
from unittest.mock import patch
from testflinger_device_connectors.devices.zapper import (
    ZapperConnector,
    logger,
)


class MockConnector(ZapperConnector):
    PROVISION_METHOD = "Test"

    def _validate_configuration(self, config, job_data):
        return (), {}


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
