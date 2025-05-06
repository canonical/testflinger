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
from collections import namedtuple
from testflinger_device_connectors.devices.maas2 import Maas2
from testflinger_device_connectors.devices import ProvisioningError
from testflinger_device_connectors.devices.maas2.maas_storage import (
    MaasStorageError,
)


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


def test_maas_cmd_retry(tmp_path):
    """
    Test that maas commands get retried when the command returns an
    exit code
    """
    Process = namedtuple("Process", ["returncode", "stdout"])
    with patch(
        "testflinger_device_connectors.devices.maas2.maas2.MaasStorage",
        return_value=None,
    ):
        with (
            patch("subprocess.run", return_value=Process(1, b"error")),
            patch("time.sleep", return_value=None) as mocked_time_sleep,
        ):
            config_yaml = tmp_path / "config.yaml"
            config = {
                "maas_user": "user",
                "node_id": "abc",
                "agent_name": "agent001",
            }
            config_yaml.write_text(yaml.safe_dump(config))

            job_json = tmp_path / "job.json"
            job = {}
            job_json.write_text(json.dumps(job))
            maas2 = Maas2(config=config_yaml, job_data=job_json)
            cmd = "my_maas_cmd"
            with pytest.raises(ProvisioningError) as err:
                maas2.run_maas_cmd_with_retry(cmd)
                assert err.messsage == "error"

            assert mocked_time_sleep.call_count == 6
