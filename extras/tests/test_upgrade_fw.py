import unittest
import upgrade_fw
import pytest
from devices import *
from unittest.mock import patch

vendor_cmd = "sudo cat /sys/class/dmi/id/chassis_vendor"
type_cmd = "sudo cat /sys/class/dmi/id/chassis_type"


class TestUpgradeFW(unittest.TestCase):
    # normal case
    def mock_run_cmd_supported(*args, **kwargs):
        if args[1] == vendor_cmd:
            return 0, "HP", ""
        elif args[1] == type_cmd:
            return 0, "13", ""

    # CID 201808-26453
    def mock_run_cmd_unsupported(*args, **kwargs):
        if args[1] == vendor_cmd:
            return 0, "Default string", ""
        elif args[1] == type_cmd:
            return 0, "3", ""

    # CID 201810-26506: no DMI info
    def mock_run_cmd_fail(*args, **kwargs):
        if args[1] == vendor_cmd:
            return (
                1,
                "cat: /sys/class/dmi/id/chassis_vendor: No such file or directory",
                "",
            )
        elif args[1] == type_cmd:
            return (
                1,
                "cat: /sys/class/dmi/id/chassis_type: No such file or directory",
                "",
            )

    # unable to SSH to DUT
    def mock_run_cmd_nossh(*args, **kwargs):
        if args[1] == vendor_cmd:
            return (
                255,
                "",
                "ssh: connect to host 10.102.161.93 port 22: No route to host",
            )
        elif args[1] == type_cmd:
            return (
                255,
                "",
                "ssh: connect to host 10.102.161.93 port 22: No route to host",
            )

    def test_detect_device_supported(self):
        with patch("devices.LVFS.LVFS.LVFSDevice.run_cmd") as mock_path:
            mock_path.side_effect = self.mock_run_cmd_supported
            device = upgrade_fw.detect_device("", "", "")
            self.assertTrue(isinstance(device, LVFSDevice))

    def test_detect_device_unsupported(self):
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            with patch("devices.LVFS.LVFS.LVFSDevice.run_cmd") as mock_path:
                mock_path.side_effect = self.mock_run_cmd_unsupported
                upgrade_fw.detect_device("", "", "")
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1

    def test_detect_device_fail(self):
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            with patch("devices.LVFS.LVFS.LVFSDevice.run_cmd") as mock_path:
                mock_path.side_effect = self.mock_run_cmd_fail
                upgrade_fw.detect_device("", "", "")
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1

    def test_detect_device_nossh(self):
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            with patch("devices.LVFS.LVFS.LVFSDevice.run_cmd") as mock_path:
                mock_path.side_effect = self.mock_run_cmd_nossh
                upgrade_fw.detect_device("", "", "")
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1
