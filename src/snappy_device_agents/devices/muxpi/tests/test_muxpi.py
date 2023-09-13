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
"""Unit tests for muxpi device agent"""

from subprocess import CalledProcessError
from snappy_device_agents.devices.muxpi.muxpi import MuxPi


def test_check_ce_oem_iot_image(mocker):
    """Test check_ce_oem_iot_image."""
    buildstamp = "iot-limerick-kria-classic-desktop-2204-x07-20230302-63"
    mocker.patch(
        "subprocess.check_output",
        return_value=buildstamp.encode(),
    )
    muxpi = MuxPi()
    assert muxpi.check_ce_oem_iot_image() is True

    buildstamp = "iot-baoshan-classic-server-2204-x04-20230807-149"
    mocker.patch(
        "subprocess.check_output",
        return_value=buildstamp.encode(),
    )
    muxpi = MuxPi()
    assert muxpi.check_ce_oem_iot_image() is True

    buildstamp = "iot-havana-core-20-ptz-gm3-uc20-20230911-2"
    mocker.patch(
        "subprocess.check_output",
        return_value=buildstamp.encode(),
    )
    muxpi = MuxPi()
    assert muxpi.check_ce_oem_iot_image() is True

    mocker.patch(
        "subprocess.check_output",
        side_effect=CalledProcessError(1, "cmd"),
    )
    assert muxpi.check_ce_oem_iot_image() is False
