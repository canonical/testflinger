"""Test LVFSDevice"""


import unittest
from unittest.mock import patch
from testflinger_device_connectors.fw_devices import HPEDevice


class TestHPEDevice(unittest.TestCase):
    @patch(
        "testflinger_device_connectors.fw_devices.HPEDevice._install_ilorest"
    )
    @patch("testflinger_device_connectors.fw_devices.HPEDevice._login_ilo")
    def test_purify_ver(self, mock_install_ilorest, mock_login_ilo):
        """Test if _purify_ver is functional"""

        mock_install_ilorest.return_value = None
        mock_login_ilo.return_value = None
        device = HPEDevice("", "", "", "", "")
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
