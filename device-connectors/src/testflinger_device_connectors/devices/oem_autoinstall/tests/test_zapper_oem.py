# Copyright (C) 2025 Canonical
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

import unittest

from testflinger_device_connectors.devices import ProvisioningError
from testflinger_device_connectors.devices.oem_autoinstall.zapper_oem import (
    ZapperOem,
)


class ZapperOemTests(unittest.TestCase):
    """Test Cases for the ZapperOem class."""

    def set_up(self):
        """Set up test fixtures."""
        self.config = {
            "device_ip": "192.168.1.100",
            "reboot_script": "/path/to/reboot.sh",
        }
        # Create a fresh device instance for each test
        self.device = ZapperOem(self.config.copy())

    def test_validate_configuration_minimal(self):
        """Test provision_data dict with minimal config."""
        self.device.job_data = {
            "provision_data": {
                "zapper_iso_url": "http://example.com/image.iso",
                "zapper_iso_type": "bootstrap",
            }
        }

        args, kwargs = self.device._validate_configuration()

        expected = {
            "zapper_iso_url": "http://example.com/image.iso",
            "zapper_iso_type": "bootstrap",
            "device_ip": "192.168.1.100",
            "username": "ubuntu",
            "password": "insecure",
            "reboot_script": "/path/to/reboot.sh",
        }

        self.assertEqual(args, ())
        self.assertDictEqual(kwargs, expected)

    def test_validate_configuration_full(self):
        """Test the function with all possible parameters."""
        self.device.job_data = {
            "provision_data": {
                "zapper_iso_url": "http://example.com/image.iso",
                "zapper_iso_type": "stock",
            },
            "test_data": {
                "test_username": "testuser",
                "test_password": "testpass",
            },
        }

        args, kwargs = self.device._validate_configuration()

        expected = {
            "zapper_iso_url": "http://example.com/image.iso",
            "zapper_iso_type": "stock",
            "device_ip": "192.168.1.100",
            "username": "testuser",
            "password": "testpass",
            "reboot_script": "/path/to/reboot.sh",
        }

        self.assertEqual(args, ())
        self.assertDictEqual(kwargs, expected)

    def test_validate_configuration_missing_required_fields(self):
        """Test exception when required fields are missing."""
        # Test missing zapper_iso_url
        self.device.job_data = {
            "provision_data": {
                "zapper_iso_type": "bootstrap",
            }
        }
        with self.assertRaises(ProvisioningError) as context:
            self.device._validate_configuration()
        self.assertIn("zapper_iso_url is required", str(context.exception))
        self.device.job_data = None  # Reset job_data

    def test_validate_configuration_missing_iso_type(self):
        """Test exception when zapper_iso_type is missing."""
        self.device.job_data = {
            "provision_data": {
                "zapper_iso_url": "http://example.com/image.iso",
            }
        }
        with self.assertRaises(ProvisioningError) as context:
            self.device._validate_configuration()
        self.assertIn("zapper_iso_type is required", str(context.exception))
        self.device.job_data = None  # Reset job_data

    def test_validate_configuration_missing_device_ip(self):
        """Test exception when device_ip is missing."""
        # Create a new device instance with empty config
        device = ZapperOem({})
        device.job_data = {
            "provision_data": {
                "zapper_iso_url": "http://example.com/image.iso",
                "zapper_iso_type": "bootstrap",
            }
        }
        with self.assertRaises(ProvisioningError) as context:
            device._validate_configuration()
        self.assertIn("device_ip is missing", str(context.exception))

    def test_validate_configuration_invalid_iso_type(self):
        """Test the function raises an exception for invalid ISO types."""
        self.device.job_data = {
            "provision_data": {
                "zapper_iso_url": "http://example.com/image.iso",
                "zapper_iso_type": "invalid_type",
            }
        }

        with self.assertRaises(ProvisioningError) as context:
            self.device._validate_configuration()
        self.assertIn("Unsupported ISO type", str(context.exception))
        self.assertIn("bootstrap", str(context.exception))
        self.assertIn("stock", str(context.exception))
        self.assertIn("bios", str(context.exception))

    def test_post_run_actions_noop(self):
        """Test that _post_run_actions does not raise any exceptions."""
        # Currently not used
        self.device._post_run_actions(None)

    def test_provision_method_constant(self):
        """Test that the PROVISION_METHOD constant is set correctly."""
        self.assertEqual(ZapperOem.PROVISION_METHOD, "ProvisioningOEM")


if __name__ == "__main__":
    unittest.main()
