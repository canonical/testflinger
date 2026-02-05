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

import base64
import unittest
from pathlib import Path

from testflinger_device_connectors.devices import ProvisioningError
from testflinger_device_connectors.devices.oem_autoinstall.zapper_oem import (
    ZapperOem,
)


class ZapperOemTests(unittest.TestCase):
    """Test Cases for the ZapperOem class."""

    def _create_device(self, config=None):
        """Create a test device with default config."""
        if config is None:
            config = {
                "device_ip": "192.168.1.100",
                "control_host": "zapper-host",
                "reboot_script": "snmp 1.2.3.4.5.6.7",
            }
        return ZapperOem(config)

    def test_validate_configuration_minimal(self):
        """Test _validate_configuration with minimal config."""
        device = self._create_device()
        device.job_data = {
            "provision_data": {
                "zapper_iso_url": "http://example.com/image.iso",
                "zapper_iso_type": "bootstrap",
            }
        }

        args, kwargs = device._validate_configuration()

        expected = {
            "zapper_iso_url": "http://example.com/image.iso",
            "zapper_iso_type": "bootstrap",
            "device_ip": "192.168.1.100",
            "update_user_data": False,
            "username": "ubuntu",
            "password": "insecure",
            "reboot_script": "snmp 1.2.3.4.5.6.7",
            "meta_data_b64": None,
            "user_data_b64": None,
            "grub_cfg_b64": None,
        }

        self.assertEqual(args, ())
        self.assertDictEqual(kwargs, expected)

    def _read_file_to_base64_test(self, filepath):
        """Return base64-encoded content of a file."""
        with open(filepath, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def test_validate_configuration_full(self):
        """Test _validate_configuration with all parameters."""
        device = self._create_device()
        device.job_data = {
            "provision_data": {
                "zapper_iso_url": "http://example.com/image.iso",
                "zapper_iso_type": "stock",
            },
            "test_data": {
                "test_username": "testuser",
                "test_password": "testpass",
            },
        }

        # Get the test data directory path
        data_dir = (
            Path(__file__).parent.parent.parent.parent
            / "data"
            / "oem_autoinstall"
            / "stock"
        )

        # Read and encode the expected files
        meta_data = self._read_file_to_base64_test(
            data_dir / "default-meta-data"
        )
        user_data = self._read_file_to_base64_test(
            data_dir / "default-user-data"
        )
        grub_cfg = self._read_file_to_base64_test(
            data_dir / "default-grub.cfg"
        )

        args, kwargs = device._validate_configuration()

        expected = {
            "zapper_iso_url": "http://example.com/image.iso",
            "zapper_iso_type": "stock",
            "device_ip": "192.168.1.100",
            "update_user_data": False,
            "username": "testuser",
            "password": "testpass",
            "reboot_script": "snmp 1.2.3.4.5.6.7",
            "meta_data_b64": meta_data,
            "user_data_b64": user_data,
            "grub_cfg_b64": grub_cfg,
        }

        self.assertEqual(args, ())
        self.assertDictEqual(kwargs, expected)

    def test_validate_configuration_missing_required_fields(self):
        """Test _validate_configuration with missing required fields."""
        device = self._create_device()
        device.job_data = {
            "provision_data": {
                "zapper_iso_type": "bootstrap",
            }
        }
        with self.assertRaises(ProvisioningError) as context:
            device._validate_configuration()
        self.assertIn("zapper_iso_url is required", str(context.exception))

    def test_validate_configuration_missing_iso_type(self):
        """Test _validate_configuration with missing zapper_iso_type."""
        device = self._create_device()
        device.job_data = {
            "provision_data": {
                "zapper_iso_url": "http://example.com/image.iso",
            }
        }
        with self.assertRaises(ProvisioningError) as context:
            device._validate_configuration()
        self.assertIn("zapper_iso_type is required", str(context.exception))

    def test_validate_configuration_missing_device_ip(self):
        """Test _validate_configuration with missing device_ip."""
        # Config with control_host but missing device_ip
        device = self._create_device(config={"control_host": "zapper-host"})
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
        """Test _validate_configuration with invalid ISO type."""
        device = self._create_device()
        device.job_data = {
            "provision_data": {
                "zapper_iso_url": "http://example.com/image.iso",
                "zapper_iso_type": "invalid_type",
            }
        }

        with self.assertRaises(ProvisioningError) as context:
            device._validate_configuration()
        self.assertIn("Unsupported ISO type", str(context.exception))
        self.assertIn("bootstrap", str(context.exception))
        self.assertIn("stock", str(context.exception))
        self.assertIn("bios", str(context.exception))

    def test_post_run_actions_noop(self):
        """Test that _post_run_actions does not raise any exceptions."""
        device = self._create_device()
        # This should not raise any exceptions
        device._post_run_actions(None)

    def test_provision_method_constant(self):
        """Test that the PROVISION_METHOD constant is set correctly."""
        self.assertEqual(ZapperOem.PROVISION_METHOD, "ProvisioningOEM")


if __name__ == "__main__":
    unittest.main()
