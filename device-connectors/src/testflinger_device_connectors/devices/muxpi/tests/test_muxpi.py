# Copyright (C) 2023 Canonical
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
"""Unit tests for muxpi device connector."""

import subprocess
from unittest.mock import MagicMock

import pytest

from testflinger_device_connectors.devices import ProvisioningError
from testflinger_device_connectors.devices.muxpi.muxpi import MuxPi


def test_check_ce_oem_iot_image(mocker):
    """Test check_ce_oem_iot_image."""
    series = "2404"
    mocker.patch(
        "subprocess.check_output",
        return_value=series.encode(),
    )
    muxpi = MuxPi()
    assert muxpi.check_ce_oem_iot_image() == "ce-oem-iot-24-and-beyond"

    series = "2204"
    mocker.patch(
        "subprocess.check_output",
        return_value=series.encode(),
    )
    muxpi = MuxPi()
    assert muxpi.check_ce_oem_iot_image() == "ce-oem-iot-before-24"

    series = "24"
    mocker.patch(
        "subprocess.check_output",
        return_value=series.encode(),
    )
    muxpi = MuxPi()
    assert muxpi.check_ce_oem_iot_image() == "ce-oem-iot-24-and-beyond"

    series = "20"
    mocker.patch(
        "subprocess.check_output",
        return_value=series.encode(),
    )
    muxpi = MuxPi()
    assert muxpi.check_ce_oem_iot_image() == "ce-oem-iot-before-24"

    mocker.patch(
        "subprocess.check_output",
        side_effect=CalledProcessError(1, "cmd"),
    )
    muxpi = MuxPi()
    assert muxpi.check_ce_oem_iot_image() is False


def test_check_test_image_booted_with_url(mocker):
    """Test check_test_image_booted with a boot_check_url."""
    muxpi = MuxPi()
    muxpi.config = {"device_ip": "1.2.3.4"}
    muxpi.job_data = {
        "provision_data": {"boot_check_url": "http://$DEVICE_IP"}
    }
    mocker.patch("time.sleep")
    mock_urlopen = mocker.patch("urllib.request.urlopen")
    mock_response = MagicMock()
    mock_response.status = 200
    mock_urlopen.return_value.__enter__.return_value = mock_response
    assert muxpi.check_test_image_booted() is True
    mock_urlopen.assert_called_once_with("http://1.2.3.4", timeout=5)


def test_check_test_image_booted_with_ssh(mocker):
    """Test check_test_image_booted with ssh."""
    muxpi = MuxPi()
    muxpi.config = {"device_ip": "1.2.3.4"}
    muxpi.job_data = {}
    mocker.patch("time.sleep")
    mock_check_output = mocker.patch("subprocess.check_output")
    assert muxpi.check_test_image_booted() is True
    assert mock_check_output.call_count == 1


def test_check_test_image_booted_fails(mocker):
    """Test check_test_image_booted when it fails."""
    muxpi = MuxPi()
    muxpi.config = {"device_ip": "1.2.3.4"}
    muxpi.job_data = {}
    mocker.patch("time.time", side_effect=[0, 1300, 1300, 1300])
    mocker.patch("time.sleep")
    mocker.patch(
        "subprocess.check_output", side_effect=CalledProcessError(1, "cmd")
    )
    with pytest.raises(ProvisioningError, match="Failed to boot test image!"):
        muxpi.check_test_image_booted()
