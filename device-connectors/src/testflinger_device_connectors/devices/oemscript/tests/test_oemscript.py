# Copyright (C) 2026 Canonical
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

"""Tests for the OemScript class."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from testflinger_device_connectors.devices.oemscript.oemscript import (
    OemScript,
)


class TestOemScript(unittest.TestCase):
    """Test cases for OemScript device connector."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures."""
        self.config_data = {
            "device_ip": "192.168.1.100",
            "agent_name": "test-agent",
            "reboot_script": ["snmpset -v1 -c private 1.2.3.4 1.3.6.1 i 1"],
        }
        self.job_data = {
            "job_id": "test-job-123",
            "provision_data": {
                "url": "http://example.com/test-image.iso",
            },
            "test_data": {
                "test_username": "ubuntu",
                "test_password": "insecure",
            },
        }

        # Create temporary files for config and job data
        self.config_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        )
        yaml.dump(self.config_data, self.config_file)
        self.config_file.close()

        self.job_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        json.dump(self.job_data, self.job_file)
        self.job_file.close()

        yield

        # Teardown
        Path(self.config_file.name).unlink(missing_ok=True)
        Path(self.job_file.name).unlink(missing_ok=True)

    def test_provision_reachable_reboots_before_provisioning(self):
        """Test the device is rebooted when it is reachable up front."""
        device = OemScript(self.config_file.name, self.job_file.name)

        with (
            patch.object(device, "copy_ssh_id") as mock_copy_ssh_id,
            patch.object(
                device, "run_on_control_host"
            ) as mock_run_on_control_host,
            patch.object(
                device, "check_device_booted"
            ) as mock_check_device_booted,
            patch.object(device, "hardreset") as mock_hardreset,
            patch.object(device, "run_recovery_script"),
        ):
            device.provision()

        # The device was reachable, so it should be rebooted over ssh and
        # we should wait for it to come back online, not hardreset.
        mock_copy_ssh_id.assert_called_once()
        mock_run_on_control_host.assert_called_once_with("sudo reboot")
        mock_hardreset.assert_not_called()
        # check_device_booted runs after the reboot and after recovery
        self.assertEqual(mock_check_device_booted.call_count, 2)

    def test_provision_unreachable_hardresets(self):
        """Test the device is hardreset when it is not reachable up front."""
        device = OemScript(self.config_file.name, self.job_file.name)

        with (
            patch.object(
                device,
                "copy_ssh_id",
                side_effect=subprocess.CalledProcessError(1, "ssh-copy-id"),
            ),
            patch.object(
                device, "run_on_control_host"
            ) as mock_run_on_control_host,
            patch.object(device, "check_device_booted"),
            patch.object(device, "hardreset") as mock_hardreset,
            patch.object(device, "run_recovery_script"),
        ):
            device.provision()

        # The device was not reachable, so it should be hardreset and
        # never rebooted over ssh.
        mock_hardreset.assert_called_once()
        mock_run_on_control_host.assert_not_called()
