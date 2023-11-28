"""Test detect_device in firmware_update.py"""


import unittest
import pytest
from unittest.mock import patch
from testflinger_device_connectors.fw_devices import LVFSDevice
from testflinger_device_connectors.fw_devices.firmware_update import (
    detect_device,
)


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
        Mock run_cmd for an Intel Desktop device (201808-26453), which
        doesn't have a supported Device class.
        """
        if args[1] == vendor_cmd:
            return 0, "Default string", ""
        elif args[1] == type_cmd:
            return 0, "3", ""

    def mock_run_cmd_fail(*args, **kwargs):
        """
        Mock run_cmd for a Rigado Cascade 500 device (201810-26506), which
        doesn't provide dmi data.
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
                "ssh: connect to host 10.102.161.93 port 22: "
                "No route to host",
            )
        elif args[1] == type_cmd:
            return (
                255,
                "",
                "ssh: connect to host 10.102.161.93 port 22: "
                "No route to host",
            )

    def test_detect_device_supported(self):
        """Test if detects_device returns a correct device class"""
        with patch(
            "testflinger_device_connectors.fw_devices.LVFSDevice.run_cmd"
        ) as mock_path:
            mock_path.side_effect = self.mock_run_cmd_supported
            device = detect_device("", "", "")
            self.assertTrue(isinstance(device, LVFSDevice))

    def test_detect_device_unsupported(self):
        """Test if detects_device exits while given a unsupported device"""
        with pytest.raises(RuntimeError) as pytest_wrapped_e:
            with patch(
                "testflinger_device_connectors.fw_devices.LVFSDevice.run_cmd"
            ) as mock_path:
                mock_path.side_effect = self.mock_run_cmd_unsupported
                detect_device("", "", "")
        self.assertEqual(pytest_wrapped_e.type, RuntimeError)
        self.assertIn(
            "is not in current support scope",
            str(pytest_wrapped_e.value),
        )

    def test_detect_device_fail(self):
        """
        Test if detects_device exits while given a device without dmi data
        """
        with pytest.raises(RuntimeError) as pytest_wrapped_e:
            with patch(
                "testflinger_device_connectors.fw_devices.LVFSDevice.run_cmd"
            ) as mock_path:
                mock_path.side_effect = self.mock_run_cmd_fail
                detect_device("", "", "")
        self.assertEqual(pytest_wrapped_e.type, RuntimeError)
        self.assertIn(
            "Unable to detect device vendor/type due to lacking of dmi info",
            str(pytest_wrapped_e.value),
        )

    def test_detect_device_nossh(self):
        """
        Test if detects_device exits while given an unreachable device
        """
        with pytest.raises(RuntimeError) as pytest_wrapped_e:
            with patch(
                "testflinger_device_connectors.fw_devices.LVFSDevice.run_cmd"
            ) as mock_path:
                mock_path.side_effect = self.mock_run_cmd_nossh
                detect_device("", "", "")
        self.assertEqual(pytest_wrapped_e.type, RuntimeError)
        self.assertIn(
            "Unable to detect device vendor/type due to lacking of dmi info",
            str(pytest_wrapped_e.value),
        )
