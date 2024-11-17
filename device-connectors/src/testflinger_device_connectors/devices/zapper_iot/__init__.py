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

"""Zapper Connector for IOT provisioning."""
import logging
from typing import Any, Dict, Tuple
from testflinger_device_connectors.devices.zapper import ZapperConnector
from testflinger_device_connectors.devices import ProvisioningError
from testflinger_device_connectors.devices.zapper_iot.parser import (
    validate_provision_plan,
    validate_url,
)

logger = logging.getLogger(__name__)


class DeviceConnector(ZapperConnector):
    """Tool for provisioning baremetal with a given image."""

    PROVISION_METHOD = "ProvisioningIoT"

    def _validate_configuration(
        self,
    ) -> Tuple[Tuple, Dict[str, Any]]:
        """
        Validate the job config and data and prepare the arguments
        for the Zapper `provision` API.
        """
        try:
            provision_plan = self.job_data["provision_data"]["provision_plan"]
            validate_provision_plan(provision_plan)
        except KeyError as e:
            raise ProvisioningError from e

        try:
            url = self.job_data["provision_data"]["url"]
            validate_url(url)
        except KeyError:
            url = []

        return ((provision_plan, url), {})
