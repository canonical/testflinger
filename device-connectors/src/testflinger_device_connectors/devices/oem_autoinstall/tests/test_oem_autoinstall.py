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

"""Tests for the OemAutoinstall class."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch

import pytest
import yaml

from testflinger_device_connectors.devices import ProvisioningError
from testflinger_device_connectors.devices.oem_autoinstall.oem_autoinstall import (  # noqa: E501
    OemAutoinstall,
)


class TestOemAutoinstall(unittest.TestCase):
    """Test cases for OemAutoinstall device connector."""

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

    def test_init(self):
        """Test OemAutoinstall initialization."""
        device = OemAutoinstall(self.config_file.name, self.job_file.name)

        self.assertEqual(device.config["device_ip"], "192.168.1.100")
        self.assertEqual(device.config["agent_name"], "test-agent")
        self.assertEqual(
            device.job_data["provision_data"]["url"],
            "http://example.com/test-image.iso",
        )

    def test_get_test_data_or_default(self):
        """Test get_test_data_or_default retrieves values correctly."""
        device = OemAutoinstall(self.config_file.name, self.job_file.name)

        # Test retrieving existing value
        username = device.get_test_data_or_default("test_username", "default")
        self.assertEqual(username, "ubuntu")

        # Test retrieving non-existent value (returns default)
        missing = device.get_test_data_or_default("missing_key", "default")
        self.assertEqual(missing, "default")

    def test_get_test_data_or_default_no_test_data(self):
        """Test get_test_data_or_default when test_data is missing."""
        job_data_no_test = {"job_id": "test", "provision_data": {}}
        job_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        json.dump(job_data_no_test, job_file)
        job_file.close()

        device = OemAutoinstall(self.config_file.name, job_file.name)
        value = device.get_test_data_or_default("test_username", "fallback")

        self.assertEqual(value, "fallback")
        Path(job_file.name).unlink()

    @patch("subprocess.check_call")
    def test_hardreset_success(self, mock_check_call):
        """Test hardreset executes reboot script successfully."""
        device = OemAutoinstall(self.config_file.name, self.job_file.name)

        device.hardreset()

        mock_check_call.assert_called_once()
        args = mock_check_call.call_args[0][0]
        self.assertIn("snmpset", args)

    @patch("subprocess.check_call")
    def test_hardreset_failure_raises_provisioning_error(
        self, mock_check_call
    ):
        """Test hardreset raises ProvisioningError on failure."""
        device = OemAutoinstall(self.config_file.name, self.job_file.name)
        mock_check_call.side_effect = subprocess.TimeoutExpired("cmd", 120)

        with self.assertRaises(ProvisioningError) as ctx:
            device.hardreset()

        self.assertIn("reboot script", str(ctx.exception))

    @patch("time.sleep")
    @patch("subprocess.check_output")
    def test_check_device_booted_success(self, mock_check_output, mock_sleep):
        """Test check_device_booted succeeds when device comes online."""
        device = OemAutoinstall(self.config_file.name, self.job_file.name)
        mock_check_output.return_value = b"success"

        result = device.check_device_booted()

        self.assertTrue(result)
        mock_check_output.assert_called()

    @patch("subprocess.run")
    def test_run_deploy_script_success(self, mock_run):
        """Test run_deploy_script executes successfully."""
        device = OemAutoinstall(self.config_file.name, self.job_file.name)
        mock_run.return_value = Mock(returncode=0)

        device.run_deploy_script("http://example.com/image.iso")

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertIn("http://example.com/image.iso", args)
        self.assertIn("192.168.1.100", args)

    @patch("subprocess.run")
    def test_run_deploy_script_failure(self, mock_run):
        """Test run_deploy_script raises ProvisioningError on failure."""
        device = OemAutoinstall(self.config_file.name, self.job_file.name)
        mock_run.return_value = Mock(returncode=1)

        with self.assertRaises(ProvisioningError) as ctx:
            device.run_deploy_script("http://example.com/image.iso")

        self.assertIn("Deploy script failed", str(ctx.exception))

    @patch("subprocess.check_call")
    @patch("subprocess.check_output")
    def test_provision_hardreset_on_ssh_failure(
        self, mock_check_output, mock_check_call
    ):
        """Test provision calls hardreset when copy_ssh_id fails."""
        device = OemAutoinstall(self.config_file.name, self.job_file.name)

        # First call (copy_ssh_id) fails, subsequent calls succeed
        mock_check_output.side_effect = [
            subprocess.CalledProcessError(1, "cmd"),
            b"success",  # After hardreset
        ]

        # Mock hardreset success
        mock_check_call.return_value = None

        # Mock other methods to prevent actual execution
        with patch.object(device, "run_deploy_script"):
            with patch.object(device, "check_device_booted"):
                with patch.object(device, "copy_to_deploy_path"):
                    with patch.object(
                        device, "prepare_storage_when_bootstrap"
                    ) as mock_prepare_storage:
                        device.provision()

        mock_prepare_storage.assert_called_once_with()

        # Verify hardreset was called
        mock_check_call.assert_called()

    @patch.object(OemAutoinstall, "copy_ssh_id")
    @patch("subprocess.run")
    def test_prepare_storage_when_in_bootstrap(
        self, mock_run, mock_copy_ssh_id
    ):
        """Test prepare-storage runs and key is restored in bootstrap."""
        device = OemAutoinstall(self.config_file.name, self.job_file.name)

        mock_run.side_effect = [
            Mock(returncode=0),  # Bootstrap detection succeeds
            Mock(returncode=1),  # Expected storage is not mounted
            Mock(returncode=0, stdout=""),  # No existing storage candidate
            Mock(returncode=0),  # Storage preparation succeeds
        ]

        device.prepare_storage_when_bootstrap()

        self.assertEqual(mock_run.call_count, 4)
        prepare_args = mock_run.call_args_list[3][0][0]
        self.assertIn(
            "sudo -n /usr/bin/prepare-storage.sh --format-partitions",
            prepare_args,
        )
        mock_copy_ssh_id.assert_called_once()

    @patch.object(OemAutoinstall, "copy_ssh_id")
    @patch("subprocess.run")
    def test_prepare_storage_skipped_when_already_mounted(
        self, mock_run, mock_copy_ssh_id
    ):
        """Test preparation is skipped for expected mounted storage."""
        device = OemAutoinstall(self.config_file.name, self.job_file.name)
        mock_run.side_effect = [Mock(returncode=0), Mock(returncode=0)]

        with patch(
            "testflinger_device_connectors.devices.oem_autoinstall."
            "oem_autoinstall.logger.info"
        ) as mock_log_info:
            device.prepare_storage_when_bootstrap()

        self.assertEqual(mock_run.call_count, 2)
        mount_check_args = mock_run.call_args_list[1][0][0]
        self.assertIn("findmnt -rn -M /home/ubuntu", mount_check_args[-1])
        self.assertIn("lsblk -dnro PARTN", mount_check_args[-1])
        mock_log_info.assert_not_called()
        mock_copy_ssh_id.assert_not_called()

    @patch.object(OemAutoinstall, "copy_ssh_id")
    @patch("subprocess.run")
    def test_existing_storage_is_mounted_before_formatting(
        self, mock_run, mock_copy_ssh_id
    ):
        """Test an existing prepared partition is mounted and reused."""
        device = OemAutoinstall(self.config_file.name, self.job_file.name)
        mock_run.side_effect = [
            Mock(returncode=0),
            Mock(returncode=1),
            Mock(returncode=0, stdout="/dev/nvme0n1p3\n"),
            Mock(returncode=0),
            Mock(returncode=0),
        ]

        device.prepare_storage_when_bootstrap()

        remote_commands = [call[0][0][-1] for call in mock_run.call_args_list]
        self.assertTrue(
            any(
                "sudo -n mount -t ext4 -o rw "
                "/dev/nvme0n1p3 /home/ubuntu" in command
                for command in remote_commands
            )
        )
        mount_command = remote_commands[3]
        self.assertLess(
            mount_command.index("cp "), mount_command.index("mount ")
        )
        self.assertLess(
            mount_command.index("mount "),
            mount_command.index("chown ubuntu:ubuntu /home/ubuntu"),
        )
        self.assertLess(
            mount_command.index("chown ubuntu:ubuntu /home/ubuntu"),
            mount_command.index("tee -a"),
        )
        self.assertFalse(
            any(
                "--format-partitions" in command for command in remote_commands
            )
        )
        mock_copy_ssh_id.assert_called_once_with(force=True)

    @patch.object(OemAutoinstall, "copy_ssh_id")
    @patch("subprocess.run")
    def test_storage_uses_configured_test_username(
        self, mock_run, mock_copy_ssh_id
    ):
        """Test storage paths and ownership use the configured test user."""
        device = OemAutoinstall(self.config_file.name, self.job_file.name)
        device.job_data["test_data"]["test_username"] = "oem"
        mock_run.side_effect = [
            Mock(returncode=0),
            Mock(returncode=1),
            Mock(returncode=0, stdout="/dev/nvme0n1p3\n"),
            Mock(returncode=0),
            Mock(returncode=0),
        ]

        device.prepare_storage_when_bootstrap()

        ssh_commands = [call[0][0] for call in mock_run.call_args_list]
        self.assertTrue(
            all("oem@192.168.1.100" in command for command in ssh_commands)
        )
        remote_commands = [command[-1] for command in ssh_commands]
        self.assertTrue(
            any(
                "findmnt -rn -M /home/oem" in command
                for command in remote_commands
            )
        )
        mount_command = remote_commands[3]
        self.assertIn("/dev/nvme0n1p3 /home/oem", mount_command)
        self.assertIn("chown oem:oem /home/oem", mount_command)
        self.assertIn("-o oem -g oem /home/oem/.ssh", mount_command)
        self.assertIn(
            "chown oem:oem /home/oem/.ssh/authorized_keys", mount_command
        )
        mock_copy_ssh_id.assert_called_once_with(force=True)

    @patch.object(OemAutoinstall, "copy_ssh_id")
    @patch("subprocess.run")
    def test_failed_mount_validation_unmounts_before_formatting(
        self, mock_run, mock_copy_ssh_id
    ):
        """Test invalid mounted storage is unmounted before formatting."""
        device = OemAutoinstall(self.config_file.name, self.job_file.name)
        mock_run.side_effect = [
            Mock(returncode=0),
            Mock(returncode=1),
            Mock(returncode=0, stdout="/dev/nvme0n1p3\n"),
            Mock(returncode=0),
            Mock(returncode=1),
            Mock(returncode=0),
            Mock(returncode=0),
        ]

        device.prepare_storage_when_bootstrap()

        remote_commands = [call[0][0][-1] for call in mock_run.call_args_list]
        umount_index = next(
            index
            for index, command in enumerate(remote_commands)
            if command == "sudo -n umount /home/ubuntu"
        )
        format_index = next(
            index
            for index, command in enumerate(remote_commands)
            if "--format-partitions" in command
        )
        self.assertLess(umount_index, format_index)
        self.assertEqual(
            mock_copy_ssh_id.call_args_list,
            [call(force=True), call()],
        )

    @patch.object(OemAutoinstall, "copy_ssh_id")
    @patch("subprocess.run")
    def test_failed_unmount_does_not_format(self, mock_run, mock_copy_ssh_id):
        """Test a failed rollback cannot format mounted storage."""
        device = OemAutoinstall(self.config_file.name, self.job_file.name)
        mock_run.side_effect = [
            Mock(returncode=0),
            Mock(returncode=1),
            Mock(returncode=0, stdout="/dev/nvme0n1p3\n"),
            Mock(returncode=0),
            Mock(returncode=1),
            Mock(returncode=1),
        ]

        device.prepare_storage_when_bootstrap()

        remote_commands = [call[0][0][-1] for call in mock_run.call_args_list]
        self.assertFalse(
            any(
                "--format-partitions" in command for command in remote_commands
            )
        )
        mock_copy_ssh_id.assert_called_once_with(force=True)

    @patch.object(OemAutoinstall, "copy_ssh_id")
    @patch("subprocess.run")
    def test_storage_inspection_failure_does_not_format(
        self, mock_run, mock_copy_ssh_id
    ):
        """Test an inspection error cannot authorize formatting."""
        device = OemAutoinstall(self.config_file.name, self.job_file.name)
        mock_run.side_effect = [
            Mock(returncode=0),
            Mock(returncode=1),
            Mock(returncode=2, stdout="", stderr="lsblk failed"),
        ]

        device.prepare_storage_when_bootstrap()

        remote_commands = [call[0][0][-1] for call in mock_run.call_args_list]
        self.assertFalse(
            any(
                "--format-partitions" in command for command in remote_commands
            )
        )
        mock_copy_ssh_id.assert_not_called()

    @patch.object(OemAutoinstall, "copy_ssh_id")
    @patch("subprocess.run")
    def test_ssh_failure_does_not_format(self, mock_run, mock_copy_ssh_id):
        """Test an SSH transport failure cannot authorize formatting."""
        device = OemAutoinstall(self.config_file.name, self.job_file.name)
        mock_run.return_value = Mock(returncode=255)

        device.prepare_storage_when_bootstrap()

        mock_run.assert_called_once()
        remote_command = mock_run.call_args[0][0][-1]
        self.assertNotIn("--format-partitions", remote_command)
        mock_copy_ssh_id.assert_not_called()

    @patch.object(OemAutoinstall, "copy_ssh_id")
    @patch("subprocess.run")
    def test_prepare_storage_when_not_in_bootstrap(
        self, mock_run, mock_copy_ssh_id
    ):
        """Test nothing happens when DUT is not in bootstrap stage."""
        device = OemAutoinstall(self.config_file.name, self.job_file.name)

        # Detection fails (c3-cid-applier absent -> not bootstrap stage)
        mock_run.return_value = Mock(returncode=1)

        device.prepare_storage_when_bootstrap()

        # Only the detection call, no prepare-storage, no re-key
        mock_run.assert_called_once()
        mock_copy_ssh_id.assert_not_called()

    @patch.object(OemAutoinstall, "copy_ssh_id")
    @patch("subprocess.run")
    def test_prepare_storage_swallows_timeout(
        self, mock_run, mock_copy_ssh_id
    ):
        """A hung/timed-out ssh call must not abort provisioning."""
        device = OemAutoinstall(self.config_file.name, self.job_file.name)

        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 30)

        device.prepare_storage_when_bootstrap()  # must not raise

        mock_copy_ssh_id.assert_not_called()

    @patch.object(OemAutoinstall, "copy_ssh_id")
    @patch("subprocess.run")
    def test_prepare_storage_swallows_format_failure(
        self, mock_run, mock_copy_ssh_id
    ):
        """A failing prepare-storage.sh must not abort provisioning."""
        device = OemAutoinstall(self.config_file.name, self.job_file.name)

        mock_run.side_effect = [
            Mock(returncode=0),
            Mock(returncode=1),
            Mock(returncode=0, stdout=""),
            Mock(returncode=1),
        ]

        device.prepare_storage_when_bootstrap()  # must not raise

        mock_copy_ssh_id.assert_called_once()

    @patch.object(OemAutoinstall, "copy_ssh_id")
    @patch("subprocess.run")
    def test_prepare_storage_swallows_copy_ssh_id_failure(
        self, mock_run, mock_copy_ssh_id
    ):
        """A failure while restoring the SSH key must not abort
        provisioning.
        """
        device = OemAutoinstall(self.config_file.name, self.job_file.name)

        mock_run.side_effect = [
            Mock(returncode=0),
            Mock(returncode=1),
            Mock(returncode=0, stdout=""),
            Mock(returncode=0),
        ]
        mock_copy_ssh_id.side_effect = subprocess.CalledProcessError(1, "cmd")

        device.prepare_storage_when_bootstrap()  # must not raise


if __name__ == "__main__":
    unittest.main()
