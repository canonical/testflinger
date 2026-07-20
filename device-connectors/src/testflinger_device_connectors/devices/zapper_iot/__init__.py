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

"""Deprecated alias for the ``control_host_iot`` connector.

This shim re-exports the connector under its old name so that agent
configurations using ``device_connector: zapper_iot`` keep working until they
migrate to ``control_host_iot``. Remove once no agents reference it.
"""

import logging
import warnings

from testflinger_device_connectors.devices.control_host_iot import (
    DeviceConnector,
)

__all__ = ["DeviceConnector"]

_DEPRECATION = (
    "The 'zapper_iot' connector is deprecated; use 'control_host_iot' instead."
)

warnings.warn(_DEPRECATION, DeprecationWarning, stacklevel=2)
logging.getLogger(__name__).warning(_DEPRECATION)
