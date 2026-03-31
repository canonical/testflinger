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

from unittest.mock import patch

import pytest
import yaml


@pytest.fixture
def mock_config():
    return {
        "maas_user": "user",
        "node_id": "abc",
        "agent_name": "agent001",
        "device_ip": "10.10.10.10",
    }


@pytest.fixture
def mock_config_file(tmp_path, mock_config):
    config_yaml = tmp_path / "config.yaml"
    config_yaml.write_text(yaml.safe_dump(mock_config))
    return config_yaml


@pytest.fixture(autouse=True)
def mock_maas_storage():
    with patch(
        "testflinger_device_connectors.devices.maas2.maas2.MaasStorage",
        return_value=None,
    ) as mock_storage:
        yield mock_storage
