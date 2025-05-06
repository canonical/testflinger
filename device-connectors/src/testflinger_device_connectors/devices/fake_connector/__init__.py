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
"""Fake device connector that can be used for testing.

It will not actually provision anything, but it will otherwise act like a
normal device connector for the other phases, such as running the test_cmds
"""

import json
import logging

from testflinger_device_connectors.devices import (
    DefaultDevice,
)

logger = logging.getLogger(__name__)


class DeviceConnector(DefaultDevice):
    """Fake device connector."""

    def provision(self, args):
        """Begin dummy provision."""
        with open(args.job_data) as json_file:
            job_data = json.load(json_file)
        provision_data = job_data.get("provision_data", {})

        logger.info("BEGIN provision")
        print("*" * 40)
        print(
            "This is a fake device connector!\n"
            "No provisioning will actually happen, but here are the values "
            "from the provision_data:"
        )
        print(json.dumps(provision_data, indent=4))
        print("*" * 40)
        logger.info("END provision")
