import unittest
import json
from devices import *
from unittest.mock import patch
from devices.LVFS.tests import fwupd_data

device_results = json.loads(fwupd_data.get_results)


class TestLVFSDevice(unittest.TestCase):
    def mock_run_cmd(*args, **kwargs):
        if "sudo fwupdmgr get-results" in args[1]:
            return 0, json.dumps(device_results), ""
        return 0, "", ""

    # current System Firmware version is the previous version
    def test_upgradable(self):
        with patch("devices.LVFS.LVFS.LVFSDevice.run_cmd") as mock_path:
            mock_path.side_effect = self.mock_run_cmd
            device = LVFSDevice("", "", "")
            print(type(fwupd_data.get_device))
            device._parse_fwupd_raw(fwupd_data.get_device)
            self.assertTrue(device.upgrade())
            self.assertFalse(device.downgrade())

    # current System Firmware version is the latest version
    def test_downgradable(self):
        with patch("devices.LVFS.LVFS.LVFSDevice.run_cmd") as mock_path:
            mock_path.side_effect = self.mock_run_cmd
            device = LVFSDevice("", "", "")

            device_info = json.loads(fwupd_data.get_device)
            device_info["Devices"][5]["Version"] = "2.91"
            device_info["Devices"][5]["Releases"][0]["Flags"] = []
            device_info["Devices"][5]["Releases"][1]["Flags"] = [
                "is-downgrade"
            ]
            device._parse_fwupd_raw(json.dumps(device_info))
            self.assertFalse(device.upgrade())
            self.assertTrue(device.downgrade())

    def test_results(self):
        global device_results
        with patch("devices.LVFS.LVFS.LVFSDevice.run_cmd") as mock_path:
            mock_path.side_effect = self.mock_run_cmd
            device = LVFSDevice("", "", "")
            device._parse_fwupd_raw(fwupd_data.get_device)

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
