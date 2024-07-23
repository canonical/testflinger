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
# along with this program.  If not, see <http://www.gnu.org/licenses/>
"""Tests for the devices module"""

from importlib import import_module
from itertools import product

import pytest

from testflinger_device_connectors.cmd import STAGES
from testflinger_device_connectors.devices import (
    DEVICE_CONNECTORS,
    get_device_stage_func,
    ProvisioningError,
)
from testflinger_device_connectors.devices.maas2.maas_storage import (
    MaasStorageError,
)

STAGES_CONNECTORS_PRODUCT = tuple(product(STAGES, DEVICE_CONNECTORS))


@pytest.mark.parametrize("stage,device", STAGES_CONNECTORS_PRODUCT)
def test_get_device_stage_func(stage, device):
    """Check that we can load all stages from all device connectors"""
    connector_instance = import_module(
        f"testflinger_device_connectors.devices.{device}"
    ).DeviceConnector()
    orig_func = getattr(connector_instance, stage)
    func = get_device_stage_func(device, stage)
    assert func.__func__ is orig_func.__func__


def test_provision_error_file_logging():
    open("provision_error.log", "w").close()
    error_message = "my error message"
    try:
        raise ProvisioningError(error_message)
    except ProvisioningError:
        with open("provision_error.log") as error_file:
            assert error_file.read() == error_message


def test_maas_storage_error_file_logging():
    open("provision_error.log", "w").close()
    error_message = "MAAS Storage Error"
    try:
        raise MaasStorageError()
    except MaasStorageError:
        with open("provision_error.log") as error_file:
            assert error_file.read() == error_message
