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

from testflinger_device_connectors.devices import (
    DefaultControlHost,
    ProvisioningError,
)
from testflinger_device_connectors.devices.muxpi import DeviceConnector
from testflinger_device_connectors.devices.muxpi.muxpi import MuxPi


def test_pre_provision_hook_uses_default_power_cycle(mocker):
    """Test that muxpi uses the default control host power cycle."""
    mocker.patch("builtins.open", mocker.mock_open())
    mock_power_cycle = mocker.patch.object(DefaultControlHost, "power_cycle")
    device = DeviceConnector(
        {
            "device_ip": "1.1.1.1",
            "control_host": "control-host",
            "control_host_reboot_script": ["reboot-cmd"],
        }
    )

    device.pre_provision_hook()

    mock_power_cycle.assert_called_once()


def test_manages_dut_power_during_reboot():
    """Test muxpi opts in to keeping the DUT off while the control host
    reboots.
    """
    assert DeviceConnector.MANAGE_DUT_POWER_DURING_REBOOT is True


def test_check_ce_oem_iot_image(mocker):
    """Test check_ce_oem_iot_image."""
    mocker.patch("time.sleep")

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
        side_effect=subprocess.CalledProcessError(1, "cmd"),
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
    mocker.patch("time.time", side_effect=[0, 1300])
    mocker.patch("time.sleep")
    mocker.patch(
        "subprocess.check_output",
        side_effect=subprocess.CalledProcessError(1, "cmd"),
    )
    with pytest.raises(ProvisioningError, match="Failed to boot test image!"):
        muxpi.check_test_image_booted()


def test_run_control_retries_until_success(mocker):
    """Test _run_control retries failures before succeeding."""
    muxpi = MuxPi()
    muxpi.config = {"control_host": "control-host", "control_user": "ubuntu"}
    mock_sleep = mocker.patch("time.sleep")
    mock_check_output = mocker.patch(
        "subprocess.check_output",
        side_effect=[subprocess.CalledProcessError(1, "cmd"), b"ok"],
    )

    out = muxpi._run_control("true")

    assert out == b"ok"
    assert mock_check_output.call_count == 2
    mock_sleep.assert_called_once_with(5)


def test_run_control_raises_after_retry_timeout(mocker):
    """Test _run_control raises when retries are exhausted."""
    muxpi = MuxPi()
    muxpi.config = {"control_host": "control-host", "control_user": "ubuntu"}
    mock_sleep = mocker.patch("time.sleep")
    mock_check_output = mocker.patch(
        "subprocess.check_output",
        side_effect=subprocess.CalledProcessError(1, "cmd", output=b"boom"),
    )

    with pytest.raises(ProvisioningError, match="boom"):
        muxpi._run_control("true")

    assert mock_check_output.call_count == 13
    assert mock_sleep.call_count == 12


@pytest.mark.parametrize(
    ("control_switch_local_cmd", "expected"),
    [
        ("sudo muxctl sdwire set TS", "sudo muxctl"),
        ("sudo -n muxctl typecmux set TS", "sudo -n muxctl"),
    ],
)
def test_control_switch_cli_cmd_returns_full_prefix(
    control_switch_local_cmd, expected
):
    """Test mux CLI detection preserves the full configured prefix."""
    muxpi = MuxPi()
    muxpi.config = {"control_switch_local_cmd": control_switch_local_cmd}

    assert muxpi._control_switch_cli_cmd() == expected


def test_storage_plug_to_self_uses_control_switch_cli_cmd(mocker):
    """Test media switching reuses the configured mux CLI command."""
    muxpi = MuxPi()
    muxpi.config = {"control_switch_local_cmd": "sudo muxctl sdwire set TS"}
    muxpi.job_data = {"provision_data": {"media": "sd"}}
    mock_run_control = mocker.patch.object(
        muxpi,
        "_run_control",
        side_effect=[b"/dev/sdX", b"/dev/usbX", b""],
    )

    with muxpi._storage_plug_to_self() as block_device:
        assert block_device == "/dev/sdX"

    assert [call.args[0] for call in mock_run_control.call_args_list] == [
        "sudo muxctl sdwire plug_to_self",
        "sudo muxctl typecmux plug_to_self",
        "sudo muxctl sdwire set DUT",
    ]


def test_storage_plug_to_self_requires_mux_cli_for_media():
    """Test media switching requires a mux-device-aware CLI command."""
    muxpi = MuxPi()
    muxpi.config = {"control_switch_local_cmd": "stm -ts"}
    muxpi.job_data = {"provision_data": {"media": "sd"}}

    with pytest.raises(ProvisioningError, match="control_switch_local_cmd"):
        with muxpi._storage_plug_to_self():
            pass


class TestMuxPiProvisionWithMuxCli:
    """Tests for MuxPi provision method with mux CLI configuration."""

    def test_provision_with_mux_cli(self, mocker):
        """Test provision proceeds normally when using a mux CLI."""
        muxpi = MuxPi()
        muxpi.config = {
            "control_switch_local_cmd": "sudo muxctl sdwire set TS",
            "control_host": "mux-control-host",
            "control_user": "ubuntu",
            "device_ip": "1.2.3.4",
            "test_device": "/dev/sda",
        }
        muxpi.job_data = {
            "provision_data": {
                "url": "http://example.com/image.img",
                "create_user": False,
            }
        }

        mocker.patch("time.sleep")
        mock_reboot_sdwire = mocker.patch.object(muxpi, "reboot_sdwire")
        # Mock the rest of provision to avoid running actual provisioning
        mocker.patch.object(muxpi, "flash_test_image")
        mocker.patch.object(muxpi, "hardreset")
        mocker.patch.object(muxpi, "check_test_image_booted")
        mocker.patch.object(muxpi, "_run_control")
        mocker.patch.object(muxpi, "run_post_provision_script")

        muxpi.provision()

        mock_reboot_sdwire.assert_not_called()

    def test_provision_without_mux_cli_reboots_sdwire(self, mocker):
        """Test provision reboots sdwire when not using a mux CLI."""
        muxpi = MuxPi()
        muxpi.config = {
            "control_switch_local_cmd": "stm -ts",
            "control_host": "control-host",
            "control_user": "ubuntu",
            "device_ip": "1.2.3.4",
            "test_device": "/dev/sda",
        }
        muxpi.job_data = {
            "provision_data": {
                "url": "http://example.com/image.img",
                "create_user": False,
            }
        }

        mocker.patch("time.sleep")
        mock_reboot_sdwire = mocker.patch.object(muxpi, "reboot_sdwire")
        # Mock the rest of provision
        mocker.patch.object(muxpi, "flash_test_image")
        mocker.patch.object(muxpi, "hardreset")
        mocker.patch.object(muxpi, "check_test_image_booted")
        mocker.patch.object(muxpi, "_run_control")
        mocker.patch.object(muxpi, "run_post_provision_script")

        muxpi.provision()

        mock_reboot_sdwire.assert_called_once()
