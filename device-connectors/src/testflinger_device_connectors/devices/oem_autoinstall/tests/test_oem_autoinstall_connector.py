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
"""Tests for the oem_autoinstall DeviceConnector provision branching."""

import json
from unittest.mock import Mock

import yaml

from testflinger_device_connectors.devices.oem_autoinstall import (
    DeviceConnector,
)

_PKG = "testflinger_device_connectors.devices.oem_autoinstall"


def _provision(mocker, tmp_path, monkeypatch, provision_data):
    monkeypatch.chdir(tmp_path)
    config = {"control_host": "control-host", "device_ip": "1.2.3.4"}
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.safe_dump(config))
    job_file = tmp_path / "job.json"
    job_file.write_text(json.dumps({"provision_data": provision_data}))

    mocker.patch(f"{_PKG}.DefaultDevice.provision")
    mocks = {
        "pre_provision": mocker.patch(f"{_PKG}.pre_provision"),
        "ControlHostOem": mocker.patch(f"{_PKG}.ControlHostOem"),
        "OemAutoinstall": mocker.patch(f"{_PKG}.OemAutoinstall"),
    }

    connector = DeviceConnector(config)
    args = Mock()
    args.config = str(config_file)
    args.job_data = str(job_file)
    connector.provision(args)
    return mocks, config


def test_generic_iso_keys_use_control_host_oem_and_skip_pre_provision(
    mocker, tmp_path, monkeypatch
):
    mocks, _ = _provision(
        mocker,
        tmp_path,
        monkeypatch,
        {
            "control_host_iso_type": "bootstrap",
            "control_host_iso_url": "http://example.com/i.iso",
        },
    )
    mocks["ControlHostOem"].return_value.provision.assert_called_once()
    mocks["pre_provision"].assert_not_called()


def test_legacy_iso_keys_fallback(mocker, tmp_path, monkeypatch):
    mocks, _ = _provision(
        mocker,
        tmp_path,
        monkeypatch,
        {
            "zapper_iso_type": "bootstrap",
            "zapper_iso_url": "http://example.com/i.iso",
        },
    )
    mocks["ControlHostOem"].return_value.provision.assert_called_once()
    mocks["pre_provision"].assert_not_called()


def test_no_iso_calls_pre_provision_and_oem_autoinstall(
    mocker, tmp_path, monkeypatch
):
    mocks, config = _provision(
        mocker,
        tmp_path,
        monkeypatch,
        {"url": "http://example.com/test-image.iso"},
    )
    mocks["pre_provision"].assert_called_once_with(config)
    mocks["ControlHostOem"].assert_not_called()
    mocks["OemAutoinstall"].return_value.provision.assert_called_once()
