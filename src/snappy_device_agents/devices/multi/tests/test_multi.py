# Copyright (C) 2023 Canonical
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

"""Unit tests for multi-device support code."""

from uuid import uuid4

import pytest
from snappy_device_agents.devices.multi.multi import Multi
from snappy_device_agents.devices.multi.tfclient import TFClient


class MockTFClient(TFClient):
    """Mock TFClient object"""

    def submit_job(self, job_data):
        """Return a fake job id"""
        return str(uuid4())


def test_bad_tfclient_url():
    """Test that Multi raises an exception when TFClient URL is bad"""
    with pytest.raises(ValueError):
        TFClient(None)
    with pytest.raises(ValueError):
        TFClient("foo.com")


def test_inject_allocate_data():
    """Test that allocate_data section is injected into job"""
    test_config = {"agent_name": "test_agent"}
    job_data = {
        "provision_data": {
            "jobs": [
                {"job_id": "1"},
                {"job_id": "2"},
            ]
        }
    }
    test_agent = Multi(test_config, job_data, MockTFClient("http://localhost"))
    test_agent.create_jobs()
    for job in test_agent.job_data["provision_data"]["jobs"]:
        assert job["allocate_data"]["allocate"] is True


def test_inject_parent_jobid():
    """Test that parent_jobid is injected into job"""
    test_config = {"agent_name": "test_agent"}
    parent_job_id = "11111111-1111-1111-1111-111111111111"
    job_data = {
        "job_id": parent_job_id,
        "provision_data": {
            "jobs": [
                {"job_id": "1"},
                {"job_id": "2"},
            ]
        },
    }
    test_agent = Multi(test_config, job_data, MockTFClient("http://localhost"))
    test_agent.create_jobs()
    for job in test_agent.job_data["provision_data"]["jobs"]:
        assert job["parent_job_id"] == parent_job_id


def test_this_job_complete():
    """Test this_job_complete() returns True only when the job is complete"""
    test_config = {"agent_name": "test_agent"}
    job_data = {
        "job_id": "11111111-1111-1111-1111-111111111111",
    }

    # completed state is complete
    complete_client = MockTFClient("http://localhost")
    complete_client.get_status = lambda job_id: "completed"
    test_agent = Multi(test_config, job_data, complete_client)
    assert test_agent.this_job_complete() is True

    # cancelled state is complete
    cancelled_client = MockTFClient("http://localhost")
    cancelled_client.get_status = lambda job_id: "cancelled"
    test_agent = Multi(test_config, job_data, cancelled_client)
    assert test_agent.this_job_complete() is True

    # anything else is not complete
    incomplete_client = MockTFClient("http://localhost")
    incomplete_client.get_status = lambda job_id: "something else"
    test_agent = Multi(test_config, job_data, incomplete_client)
    assert test_agent.this_job_complete() is False
