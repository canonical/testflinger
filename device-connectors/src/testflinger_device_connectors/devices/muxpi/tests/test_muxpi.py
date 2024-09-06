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
"""Unit tests for muxpi device connector"""

from subprocess import CalledProcessError
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
    assert muxpi.check_ce_oem_iot_image() is False
