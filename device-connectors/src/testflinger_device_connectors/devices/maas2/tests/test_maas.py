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

"""Maas2 agent module unit tests."""


import json
import pytest
import yaml
from unittest.mock import patch
from testflinger_device_connectors.devices.maas2 import Maas2
from testflinger_device_connectors.devices import ProvisioningError
from testflinger_device_connectors.devices.maas2.maas_storage import (
    MaasStorageError,
)


@pytest.fixture
def dummy_maas2(tmp_path):
    config_yaml = tmp_path / "config.yaml"
    config = {"maas_user": "user", "node_id": "abc", "agent_name": "agent001"}
    config_yaml.write_text(yaml.safe_dump(config))

    job_json = tmp_path / "job.json"
    job = {"provision_data": {}}
    job_json.write_text(json.dumps(job))

    with patch(
        "testflinger_device_connectors.devices.maas2.maas2.MaasStorage",
        return_value=None,
    ):
        return Maas2(config=config_yaml, job_data=job_json)


def test_maas2_agent_invalid_storage(tmp_path):
    """Test that the maas2 agent raises an exception when storage init fails"""
    config_yaml = tmp_path / "config.yaml"
    config = {"maas_user": "user", "node_id": "abc", "agent_name": "agent001"}
    config_yaml.write_text(yaml.safe_dump(config))

    job_json = tmp_path / "job.json"
    job = {}
    job_json.write_text(json.dumps(job))

    with pytest.raises(MaasStorageError) as err:
        Maas2(config=config_yaml, job_data=job_json)

    # MaasStorageError should also be a subclass of ProvisioningError
    assert isinstance(err.value, ProvisioningError)


def test_maas2_error_file_logging(dummy_maas2):
    open("provision-error.json", "w").close()
    error_message = "my error message"
    exception_info = {
        "exception_name": "ProvisioningError",
        "exception_message": error_message,
        "exception_cause": "MaasStorageError()",
    }
    with patch.object(Maas2, "deploy_node") as mock_deploy_node:
        provisioning_error = ProvisioningError(error_message)
        provisioning_error.__cause__ = MaasStorageError()
        mock_deploy_node.side_effect = provisioning_error
        try:
            dummy_maas2.provision()
        except Exception:
            with open("provision-error.json") as error_file:
                assert (
                    json.loads(error_file.read())["exception_info"]
                    == exception_info
                )
