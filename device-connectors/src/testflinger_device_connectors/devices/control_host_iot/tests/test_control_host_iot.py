# Copyright (C) 2024 Canonical
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
"""Unit tests for the control host IoT device connector."""

import unittest
from unittest.mock import MagicMock, patch

from testflinger_device_connectors.devices import ProvisioningError
from testflinger_device_connectors.devices.control_host_iot import (
    DeviceConnector,
)


class ControlHostIoTTests(unittest.TestCase):
    """Test cases for the control host IoT connector."""

    def test_provision_method(self):
        self.assertEqual(DeviceConnector.PROVISION_METHOD, "iot")

    def test_manages_dut_power_during_reboot(self):
        """control_host_iot opts in to keeping the DUT off while the control
        host reboots, unlike the base connector and other variants.
        """
        self.assertTrue(DeviceConnector.MANAGE_DUT_POWER_DURING_REBOOT)

    @patch(
        "testflinger_device_connectors.devices.control_host_iot.SerialLogger"
    )
    @patch(
        "testflinger_device_connectors.devices.control_host"
        ".ControlHostConnector.provision"
    )
    def test_provision_wraps_super_with_serial_logger(
        self, mock_super_provision, mock_serial_logger_factory
    ):
        """Test that provision starts SerialLogger before provisioning
        and stops it afterwards.
        """
        mock_serial_proc = MagicMock()
        mock_serial_logger_factory.return_value = mock_serial_proc

        device = DeviceConnector(
            {
                "control_host": "control-host",
                "serial_host": "serial-host",
                "serial_port": 3000,
            }
        )
        args = MagicMock()
        device.provision(args)

        mock_serial_logger_factory.assert_called_once_with(
            "serial-host", 3000, "provision-serial.log"
        )
        mock_serial_proc.start.assert_called_once()
        mock_super_provision.assert_called_once_with(args)
        mock_serial_proc.stop.assert_called_once()

    @patch(
        "testflinger_device_connectors.devices.control_host_iot.SerialLogger"
    )
    @patch(
        "testflinger_device_connectors.devices.control_host"
        ".ControlHostConnector.provision"
    )
    def test_provision_stops_serial_logger_on_failure(
        self, mock_super_provision, mock_serial_logger_factory
    ):
        """Test that SerialLogger is stopped even when provisioning fails."""
        mock_serial_proc = MagicMock()
        mock_serial_logger_factory.return_value = mock_serial_proc
        mock_super_provision.side_effect = ProvisioningError("fail")

        device = DeviceConnector(
            {
                "control_host": "control-host",
                "serial_host": "serial-host",
                "serial_port": 3000,
            }
        )

        with self.assertRaises(ProvisioningError):
            device.provision(MagicMock())

        mock_serial_proc.start.assert_called_once()
        mock_serial_proc.stop.assert_called_once()

    @patch.object(DeviceConnector, "_copy_ssh_id")
    def test_post_run_actions_copy_ssh_id_no_provision_plan(
        self, mock_copy_ssh_id
    ):
        """Copy the ssh id when there is no provision plan and no
        ubuntu_sso_email.
        """
        device = DeviceConnector(
            {"device_ip": "1.1.1.1", "control_host": "control-host"}
        )
        device.job_data = {"provision_data": {}}
        device._post_run_actions(args=None)
        mock_copy_ssh_id.assert_called_once()

    @patch.object(DeviceConnector, "_copy_ssh_id")
    def test_post_run_actions_not_copy_ssh_id_ubuntu_sso_email(
        self, mock_copy_ssh_id
    ):
        """Do not copy the ssh id when ubuntu_sso_email is set."""
        device = DeviceConnector(
            {"device_ip": "1.1.1.1", "control_host": "control-host"}
        )
        device.job_data = {
            "provision_data": {"ubuntu_sso_email": "test@example.com"}
        }
        device._post_run_actions(args=None)
        mock_copy_ssh_id.assert_not_called()

    @patch.object(DeviceConnector, "_copy_ssh_id")
    def test_post_run_actions_not_copy_ssh_id_no_agent_ssh_access(
        self, mock_copy_ssh_id
    ):
        """Do not copy the ssh id when agent_ssh_access is false."""
        device = DeviceConnector(
            {"device_ip": "1.1.1.1", "control_host": "control-host"}
        )
        device.job_data = {"provision_data": {"agent_ssh_access": False}}
        device._post_run_actions(args=None)
        mock_copy_ssh_id.assert_not_called()

    @patch.object(DeviceConnector, "_copy_ssh_id")
    def test_post_run_actions_copy_ssh_id_provision_plan(
        self, mock_copy_ssh_id
    ):
        """Copy the ssh id when initial login is not console-conf."""
        device = DeviceConnector(
            {"device_ip": "1.1.1.1", "control_host": "control-host"}
        )
        device.job_data = {
            "provision_data": {
                "provision_plan": {
                    "run_stage": [{"initial_login": {"method": "system-user"}}]
                }
            }
        }
        device._post_run_actions(args=None)
        mock_copy_ssh_id.assert_called_once()


if __name__ == "__main__":
    unittest.main()
