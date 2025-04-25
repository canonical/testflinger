"""Test LVFSDevice"""

import json
import unittest
from unittest.mock import patch

from testflinger_device_connectors.fw_devices import (
    FwupdUpdateState,
    LVFSDevice,
)
from testflinger_device_connectors.fw_devices.LVFS.tests import fwupd_data

device_results = json.loads(fwupd_data.GET_RESULTS_RESPONSE_DATA)


class TestLVFSDevice(unittest.TestCase):
    def mock_run_cmd(*args, **kwargs):
        """Mock run_cmd"""
        if "sudo fwupdmgr get-results" in args[1]:
            return 0, json.dumps(device_results), ""
        return 0, "", ""

    def test_upgradable(self):
        """
        Given fwupd data with only newer System Firmware releases available.
        Test if upgrade function returns True. And test if downgrade function
        returns False.
        """
        with patch(
            "testflinger_device_connectors.fw_devices.LVFSDevice.run_cmd"
        ) as mock_path:
            mock_path.side_effect = self.mock_run_cmd
            device = LVFSDevice("", "", "")
            device._parse_fwupd_raw(fwupd_data.GET_DEVICES_RESPONSE_DATA)
            self.assertTrue(device.upgrade())
            self.assertFalse(device.downgrade())

    def test_downgradable(self):
        """
        Given fwupd data with only older System Firmware releases available.
        Test if upgrade function returns False. And test if downgrade function
        returns True.
        """
        with patch(
            "testflinger_device_connectors.fw_devices.LVFSDevice.run_cmd"
        ) as mock_path:
            mock_path.side_effect = self.mock_run_cmd
            device = LVFSDevice("", "", "")

            device_info = json.loads(fwupd_data.GET_DEVICES_RESPONSE_DATA)
            device_info["Devices"][5]["Version"] = "2.91"
            device_info["Devices"][5]["Releases"][0]["Flags"] = []
            device_info["Devices"][5]["Releases"][1]["Flags"] = [
                "is-downgrade"
            ]
            device._parse_fwupd_raw(json.dumps(device_info))
            self.assertFalse(device.upgrade())
            self.assertTrue(device.downgrade())

    def test_check_results_failed_state(self):
        """Validate UpdateState check in check_results"""
        global device_results
        with patch(
            "testflinger_device_connectors.fw_devices.LVFSDevice.run_cmd"
        ) as mock_path:
            mock_path.side_effect = self.mock_run_cmd
            device = LVFSDevice("", "", "")
            device._parse_fwupd_raw(fwupd_data.GET_DEVICES_RESPONSE_DATA)
            device.fw_info[2]["targetVersion"] = "2.90"
            device_results = json.loads(fwupd_data.GET_RESULTS_RESPONSE_DATA)
            device_results["UpdateState"] = 3
            self.assertFalse(device.check_results())

    def test_check_results_mismatched_version(self):
        """Validate version check in check_results"""
        with patch(
            "testflinger_device_connectors.fw_devices.LVFSDevice.run_cmd"
        ) as mock_path:
            mock_path.side_effect = self.mock_run_cmd
            device = LVFSDevice("", "", "")
            device._parse_fwupd_raw(fwupd_data.GET_DEVICES_RESPONSE_DATA)
            device.fw_info[2]["targetVersion"] = "2.91"
            self.assertFalse(device.check_results())

    def test_check_results_good(self):
        """Test if check_results works with a valid case"""
        global device_results
        with patch(
            "testflinger_device_connectors.fw_devices.LVFSDevice.run_cmd"
        ) as mock_path:
            mock_path.side_effect = self.mock_run_cmd
            device = LVFSDevice("", "", "")
            device._parse_fwupd_raw(fwupd_data.GET_DEVICES_RESPONSE_DATA)
            device_results = json.loads(fwupd_data.GET_RESULTS_RESPONSE_DATA)
            device_results["UpdateState"] = (
                FwupdUpdateState.FWUPD_UPDATE_STATE_SUCCESS.value
            )
            device_results["Releases"][0]["Version"] = "2.90"
            device.fw_info[2]["targetVersion"] = "2.90"
            self.assertTrue(device.check_results())

    def test_check_results_error(self):
        """
        Test error in check_results with an error return from ```$ fwupdmgr
        get-results```
        """
        global device_results
        with patch(
            "testflinger_device_connectors.fw_devices.LVFSDevice.run_cmd"
        ) as mock_path:
            mock_path.side_effect = self.mock_run_cmd
            device = LVFSDevice("", "", "")
            device._parse_fwupd_raw(fwupd_data.GET_DEVICES_RESPONSE_DATA)
            device.fw_info[2]["targetVersion"] = "2.90"
            device_results = json.loads(
                fwupd_data.GET_RESULTS_ERROR_RESPONSE_DATA
            )
            self.assertFalse(device.check_results())
