# Copyright (C) 2023 Canonical
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

"""Ubuntu OEM Script provisioning for OEM devices with Ubuntu Noble series
For systems that use the oem image-deploy.sh script for provisioning
"""

import logging
from testflinger_device_connectors.devices.oemscript.oemscript import OemScript

logger = logging.getLogger(__name__)


class NobleOemScript(OemScript):
    """Device Agent for Noble OEM devices."""

    distro = "noble"
