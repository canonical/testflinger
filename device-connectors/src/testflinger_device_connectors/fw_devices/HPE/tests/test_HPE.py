"""Test HPEDevice"""

import unittest
import json
import os
from unittest.mock import patch, Mock
from testflinger_device_connectors.fw_devices import (
    HPEDevice,
    FirmwareUpdateError,
)
from testflinger_device_connectors.fw_devices.HPE.tests import HPE_data

HPEDevice_path = "testflinger_device_connectors.fw_devices.HPEDevice"
get_fw_cmd = "rawget /redfish/v1/UpdateService/FirmwareInventory/"
get_sysinfo_cmd = "systeminfo --system --json"


class TestHPEDevice(unittest.TestCase):
    def test_init_invalid_bmc_ip(self):
        """
        Test if FirmwareUpdateError raises given a invalid BMC IP address
        """
        with self.assertRaises(FirmwareUpdateError):
            HPEDevice("", "", "300.0.0.0", "", "")

    def test_init_null_bmc_ip(self):
        """
        Test if FirmwareUpdateError raises given a null BMC IP address
        """
        with self.assertRaises(FirmwareUpdateError):
            HPEDevice("", "", "", "", "")

    def test_purify_ver(self):
        """Test if _purify_ver is functional"""

        with patch(f"{HPEDevice_path}._install_ilorest") as mock1, patch(
            f"{HPEDevice_path}._login_ilo"
        ) as mock2:
            mock1.return_value = None
            mock2.return_value = None
            device = HPEDevice("", "", "127.0.0.1", "", "")
        self.assertEqual(
            device._purify_ver("U30 v2.76 (02/09/2023)"),
            device._purify_ver("2.76_02-09-2023"),
        )
        self.assertEqual(
            device._purify_ver("4.1.4.901"),
            device._purify_ver("04.01.04.901"),
        )
        self.assertEqual(
            device._purify_ver("2.96 Aug 17 2023"),
            device._purify_ver("2.96"),
        )
        self.assertNotEqual(
            device._purify_ver("U30 v2.76 (02/09/2023)"),
            device._purify_ver("2.76_02-90-2023"),
        )
        self.assertNotEqual(
            device._purify_ver("4.1.4.901"),
            device._purify_ver("04.010.04.901"),
        )
        self.assertEqual(
            device._purify_ver("08.65.08"),
            device._purify_ver("8.65.08"),
        )

    def mock_run_cmd(*args, **kwargs):
        """
        Mock run_cmd for ilorest calls
        """
        if get_fw_cmd in args[1]:
            return 0, HPE_data.RAWGET_FIRMWARE_INVENTORY, ""
        elif args[1] == get_sysinfo_cmd:
            return 0, HPE_data.SYSTEMINFO_SYSTEM, ""
        else:
            return 0, "", ""

    def test_get_fw_info(self):
        """
        Test if all raw FirmwareInventory data transferred to HPEDevice.fw_info
        """
        with patch(f"{HPEDevice_path}._install_ilorest") as mock1, patch(
            f"{HPEDevice_path}._login_ilo"
        ) as mock2:
            mock1.return_value = None
            mock2.return_value = None
            device = HPEDevice("", "", "127.0.0.1", "", "")
        with patch(f"{HPEDevice_path}.run_cmd") as mock1:
            mock1.side_effect = self.mock_run_cmd
            device.get_fw_info()

        for member in json.loads(HPE_data.RAWGET_FIRMWARE_INVENTORY)[
            "Members"
        ]:
            self.assertTrue(
                any(member["Name"] in fw.values() for fw in device.fw_info)
            )

    def mock_download_file(*args, **kwargs):
        with open(
            os.path.join(
                os.path.dirname(__file__), "mock_hpe_fwpp-gen10.html"
            ),
            "r",
        ) as file:
            fwrepo = file.read()
        mock_response = Mock()
        mock_response.text = fwrepo
        return mock_response

    def test_flash_fwpkg(self):
        """
        Test if FirmwareUpdateError is raised given a non-supported SPP version
        """
        with patch(f"{HPEDevice_path}._install_ilorest") as mock1, patch(
            f"{HPEDevice_path}._login_ilo"
        ) as mock2:
            mock1.return_value = None
            mock2.return_value = None
            device = HPEDevice("", "", "127.0.0.1", "", "")

        with patch(f"{HPEDevice_path}.run_cmd") as mock1, patch(
            f"{HPEDevice_path}._download_file"
        ) as mock2:
            mock1.side_effect = self.mock_run_cmd
            mock2.side_effect = self.mock_download_file
            device._get_hpe_fw_repo()
        with self.assertRaises(FirmwareUpdateError):
            device._flash_fwpkg("2023.09.10.04")
