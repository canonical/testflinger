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
"""Tests for the oemscript connector's control-host pre_provision call."""

from unittest.mock import Mock

import yaml

from testflinger_device_connectors.devices.oemscript import DeviceConnector


def test_provision_calls_control_host_pre_provision(
    mocker, tmp_path, monkeypatch
):
    """The oemscript connector delegates USB-stick removal to the control
    host's best-effort pre_provision phase.
    """
    monkeypatch.chdir(tmp_path)
    config = {"control_host": "control-host", "device_ip": "1.2.3.4"}
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.safe_dump(config))

    mocker.patch(
        "testflinger_device_connectors.devices.oemscript"
        ".DefaultDevice.provision"
    )
    mock_pre = mocker.patch(
        "testflinger_device_connectors.devices.oemscript.pre_provision"
    )
    mock_oem = mocker.patch(
        "testflinger_device_connectors.devices.oemscript.OemScript"
    )

    connector = DeviceConnector(config)
    args = Mock()
    args.config = str(config_file)
    args.job_data = "job.json"
    connector.provision(args)

    mock_pre.assert_called_once_with(config)
    mock_oem.return_value.provision.assert_called_once()
