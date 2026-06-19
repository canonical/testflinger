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
"""Tests for the deprecated zapper_kvm alias shim."""

import importlib
import warnings


def test_shim_reexports_control_host_kvm_connector():
    """The deprecated zapper_kvm module re-exports the control_host_kvm
    DeviceConnector class.
    """
    shim = importlib.import_module(
        "testflinger_device_connectors.devices.zapper_kvm"
    )
    new = importlib.import_module(
        "testflinger_device_connectors.devices.control_host_kvm"
    )
    assert shim.DeviceConnector is new.DeviceConnector


def test_shim_emits_deprecation_warning_on_import():
    """Importing the deprecated module emits a DeprecationWarning."""
    module = importlib.import_module(
        "testflinger_device_connectors.devices.zapper_kvm"
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        importlib.reload(module)
    assert any(
        issubclass(w.category, DeprecationWarning)
        and "control_host_kvm" in str(w.message)
        for w in caught
    )
