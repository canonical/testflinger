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

"""Control host connector for OEM ISO provisioning.

The provisioning payload (ISO type validation, stock-ISO defaults) is built
by the control host service; this connector is a thin client with no post-run
actions.
"""

import logging

from testflinger_device_connectors.devices.control_host import (
    ControlHostConnector,
)

logger = logging.getLogger(__name__)


class ControlHostOem(ControlHostConnector):
    PROVISION_METHOD = "oem"

    def _post_run_actions(self, args):
        pass
