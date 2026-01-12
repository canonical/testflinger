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
