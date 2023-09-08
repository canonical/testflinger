import unittest
import json
from devices import *
from unittest.mock import patch
from devices.LVFS.tests import fwupd_data

device_info = json.loads(fwupd_data.get_device)
device_results = json.loads(fwupd_data.get_results)


class TestLVFSDevice(unittest.TestCase):
    def mock_run_ssh(*args, **kwargs):
        global device_info
        global device_results
        if args[1] == "sudo fwupdmgr refresh --force":
            return 0, "", ""
        elif args[1] == "sudo fwupdmgr get-devices --json":
            return 0, json.dumps(device_info), ""
        elif "sudo fwupdmgr upgrade" in args[1]:
            return 0, "", ""
        elif "sudo fwupdmgr download" in args[1]:
            return 0, "", ""
        elif "sudo fwupdmgr install" in args[1]:
            return 0, "", ""
        elif "sudo fwupdmgr get-results" in args[1]:
            return 0, json.dumps(device_results), ""

    # current System Firmware version is the previous version
    def test_upgradable(self):
        global device_info
        device_info = json.loads(fwupd_data.get_device)
        with patch("devices.LVFS.LVFS.LVFSDevice.run_cmd") as mock_path:
            mock_path.side_effect = self.mock_run_ssh
            device = LVFSDevice("", "", "")

            device.get_fw_info()
            self.assertTrue(device.upgrade())
            self.assertFalse(device.downgrade())

    # current System Firmware version is the latest version
    def test_downgradable(self):
        global device_info
        device_info = json.loads(fwupd_data.get_device)
        with patch("devices.LVFS.LVFS.LVFSDevice.run_cmd") as mock_path:
            mock_path.side_effect = self.mock_run_ssh
            device = LVFSDevice("", "", "")

            device_info["Devices"][5]["Version"] = "2.91"
            device_info["Devices"][5]["Releases"][0]["Flags"] = []
            device_info["Devices"][5]["Releases"][1]["Flags"] = [
                "is-downgrade"
            ]
            device.get_fw_info()
            self.assertFalse(device.upgrade())
            self.assertTrue(device.downgrade())

    def test_results(self):
        global device_results
        with patch("devices.LVFS.LVFS.LVFSDevice.run_cmd") as mock_path:
            mock_path.side_effect = self.mock_run_ssh
            device = LVFSDevice("", "", "")
            device.get_fw_info()

            # validate UpdateState check in check_results()
            device.fw_info[2]["targetVersion"] = "2.90"
            device_results["UpdateState"] = 3
            self.assertFalse(device.check_results())

            # validate version check in check_results()
            device.fw_info[2]["targetVersion"] = "2.91"
            self.assertFalse(device.check_results())

            # validate a successful case in check_results()
            device_results["UpdateState"] = 2
            device_results["Releases"][0]["Version"] = "2.90"
            device.fw_info[2]["targetVersion"] = "2.90"
            self.assertTrue(device.check_results())

            # validate an error return of $fwupdmgr get-results
            device_results = json.loads(fwupd_data.get_results_err)
            self.assertFalse(device.check_results())
