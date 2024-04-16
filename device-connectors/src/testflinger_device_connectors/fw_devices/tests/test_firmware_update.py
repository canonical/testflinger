"""Test detect_device in firmware_update.py"""

import unittest
import pytest
from unittest.mock import patch
from testflinger_device_connectors.fw_devices import (
    LVFSDevice,
    FirmwareUpdateError,
)
from testflinger_device_connectors.fw_devices.firmware_update import (
    detect_device,
)

LVFSDevice_path = "testflinger_device_connectors.fw_devices.LVFSDevice"
vendor_cmd = "sudo cat /sys/class/dmi/id/chassis_vendor"
type_cmd = "sudo cat /sys/class/dmi/id/chassis_type"


class TestFirmwareUpdate(unittest.TestCase):
    def mock_run_cmd_supported(*args, **kwargs):
        """
        Mock run_cmd for a HP All In One device, which has a supported
        Device class.
        """
        if args[1] == vendor_cmd:
            return 0, "HP", ""
        elif args[1] == type_cmd:
            return 0, "13", ""

    def mock_run_cmd_unsupported(*args, **kwargs):
        """
        Mock run_cmd for a device which doesn't have a supported Device class.
        """
        if args[1] == vendor_cmd:
            return 0, "Default string", ""
        elif args[1] == type_cmd:
            return 0, "3", ""

    def mock_run_cmd_fail(*args, **kwargs):
        """
        Mock run_cmd for a device which couldn't provide dmi data.
        """
        if args[1] == vendor_cmd:
            return (
                1,
                "cat: /sys/class/dmi/id/chassis_vendor: "
                "No such file or directory",
                "",
            )
        elif args[1] == type_cmd:
            return (
                1,
                "cat: /sys/class/dmi/id/chassis_type: "
                "No such file or directory",
                "",
            )

    def mock_run_cmd_nossh(*args, **kwargs):
        """
        Mock run_cmd to simulate an unreachable device.
        """
        if args[1] == vendor_cmd:
            return (
                255,
                "",
                "ssh: connect to host 10.10.10.10 port 22: "
                "No route to host",
            )
        elif args[1] == type_cmd:
            return (
                255,
                "",
                "ssh: connect to host 10.10.10.10 port 22: "
                "No route to host",
            )

    def test_detect_device_supported(self):
        """Test if detects_device returns a correct device class"""
        with patch(f"{LVFSDevice_path}.run_cmd") as mock1, patch(
            f"{LVFSDevice_path}.check_connectable"
        ) as mock2:
            mock1.side_effect = self.mock_run_cmd_supported
            mock2.return_value = None
            device = detect_device("", "", "")
            self.assertTrue(isinstance(device, LVFSDevice))

    def test_detect_device_unsupported(self):
        """Test if detects_device exits while given a unsupported device"""
        with pytest.raises(FirmwareUpdateError) as pytest_wrapped_e:
            with patch(f"{LVFSDevice_path}.run_cmd") as mock1, patch(
                f"{LVFSDevice_path}.check_connectable"
            ) as mock2:
                mock1.side_effect = self.mock_run_cmd_unsupported
                mock2.return_value = None
                detect_device("", "", "")
            self.assertIn(
                "is not in current support scope",
                str(pytest_wrapped_e.value),
            )

    def test_detect_device_fail(self):
        """
        Test if detects_device exits while given a device without dmi data
        """
        with pytest.raises(FirmwareUpdateError) as pytest_wrapped_e:
            with patch(f"{LVFSDevice_path}.run_cmd") as mock1, patch(
                f"{LVFSDevice_path}.check_connectable"
            ) as mock2:
                mock1.side_effect = self.mock_run_cmd_fail
                mock2.return_value = None
                detect_device("", "", "")
            self.assertIn(
                "Unable to detect device vendor/type due to lacking of dmi",
                str(pytest_wrapped_e.value),
            )

    def test_detect_device_nossh(self):
        """
        Test if detects_device exits while given an unreachable device
        """
        with pytest.raises(FirmwareUpdateError) as pytest_wrapped_e:
            with patch(f"{LVFSDevice_path}.run_cmd") as mock1, patch(
                f"{LVFSDevice_path}.check_connectable"
            ) as mock2:
                mock1.side_effect = self.mock_run_cmd_nossh
                mock2.return_value = None
                detect_device("", "", "")
            self.assertIn(
                "Unable to detect device vendor/type due to lacking of dmi",
                str(pytest_wrapped_e.value),
            )
