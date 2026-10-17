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

"""Unit tests for the multi-device DeviceConnector."""

import json
from types import SimpleNamespace

import yaml

from testflinger_device_connectors.devices.multi import DeviceConnector


def _make_connector() -> DeviceConnector:
    """Create a DeviceConnector instance without running __init__."""
    return DeviceConnector.__new__(DeviceConnector)


def test_init_device_passes_credentials_to_tfclient(tmp_path, mocker):
    """Test that init_device passes credentials to TFClient."""
    config = {
        "testflinger_server": "http://testflinger.example.com",
        "client_id": "my-client-id",
        "secret_key": "my-secret-key",
        "agent_name": "test_agent",
    }
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.safe_dump(config))

    job_data = {"job_id": "1234"}
    job_data_file = tmp_path / "testflinger.json"
    job_data_file.write_text(json.dumps(job_data))

    args = SimpleNamespace(
        config=str(config_file), job_data=str(job_data_file)
    )

    mock_tfclient = mocker.patch(
        "testflinger_device_connectors.devices.multi.TFClient"
    )
    mock_multi = mocker.patch(
        "testflinger_device_connectors.devices.multi.Multi"
    )

    connector = _make_connector()
    connector.init_device(args)

    # If authentication is enabled server side, the TFClient should be
    # initialized with the provided credentials.
    mock_tfclient.assert_called_once_with(
        url="http://testflinger.example.com",
        client_id="my-client-id",
        secret_key="my-secret-key",  # noqa: S106
    )
    mock_multi.assert_called_once_with(
        config, job_data, mock_tfclient.return_value
    )
    assert connector.device == mock_multi.return_value


def test_init_device_without_credentials(tmp_path, mocker):
    """Test that init_device passes no credentials to TFClient."""
    config = {
        "testflinger_server": "http://testflinger.example.com",
        "agent_name": "test_agent",
    }
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.safe_dump(config))

    job_data_file = tmp_path / "testflinger.json"
    job_data_file.write_text(json.dumps({"job_id": "1234"}))

    args = SimpleNamespace(
        config=str(config_file), job_data=str(job_data_file)
    )

    mock_tfclient = mocker.patch(
        "testflinger_device_connectors.devices.multi.TFClient"
    )
    mocker.patch("testflinger_device_connectors.devices.multi.Multi")

    connector = _make_connector()
    connector.init_device(args)

    # TFclient should be allowed to be initialized without credentials.
    # This is in case OIDC is not enabled server side as authentication is not
    # required for multi-device connectors to function.
    mock_tfclient.assert_called_once_with(
        url="http://testflinger.example.com",
        client_id=None,
        secret_key=None,
    )


def test_get_job_list_data_missing_file(tmp_path):
    """Test that empty list is returned when the file doesn't exist."""
    connector = _make_connector()
    missing_file = tmp_path / "attachments" / ".job-list.json"

    result = connector.get_job_list_data(missing_file)

    assert result == []


def test_get_job_list_data_reads_existing_file(tmp_path):
    """Test that job list data is read from an existing file."""
    connector = _make_connector()
    job_list_file = tmp_path / "attachments" / ".job-list.json"
    job_list_file.parent.mkdir(parents=True)
    expected_data = [
        {"job_id": "1234", "device_info": {"device_ip": "10.1.1.1"}}
    ]
    job_list_file.write_text(json.dumps(expected_data))

    result = connector.get_job_list_data(job_list_file)

    assert result == expected_data
