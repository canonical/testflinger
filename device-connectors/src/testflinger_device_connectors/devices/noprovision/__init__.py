# Copyright (C) 2017-2023 Canonical
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

"""Noprovision support code."""

import logging

import testflinger_device_connectors
from testflinger_device_connectors.devices import (
    DefaultDevice,
)
from testflinger_device_connectors.devices.noprovision.noprovision import (
    Noprovision,
)

logger = logging.getLogger(__name__)


class DeviceConnector(DefaultDevice):
    def provision(self, args):
        device = Noprovision(args.config)
        test_username = testflinger_device_connectors.get_test_username(
            args.job_data
        )
        logger.info("BEGIN provision")
        device.ensure_test_image(test_username)
        logger.info("END provision")
