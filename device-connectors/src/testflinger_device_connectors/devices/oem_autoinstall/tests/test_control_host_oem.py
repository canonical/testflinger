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

from testflinger_device_connectors.devices.oem_autoinstall.control_host_oem import (  # noqa: E501
    ControlHostOem,
)


class ControlHostOemTests(unittest.TestCase):
    """Test cases for the ControlHostOem connector."""

    def test_provision_method_constant(self):
        self.assertEqual(ControlHostOem.PROVISION_METHOD, "oem")

    def test_post_run_actions_noop(self):
        """_post_run_actions does not raise any exceptions."""
        device = ControlHostOem(
            {
                "device_ip": "192.168.1.100",
                "control_host": "control-host",
                "reboot_script": "snmp 1.2.3.4.5.6.7",
            }
        )
        device._post_run_actions(None)


if __name__ == "__main__":
    unittest.main()
