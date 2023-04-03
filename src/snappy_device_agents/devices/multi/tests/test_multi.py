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
from snappy_device_agents.devices.multi.multi import Multi
from snappy_device_agents.devices.multi.tfclient import TFClient


class MockTFClient(TFClient):
    """Mock TFClient object"""

    def submit_job(self, job_data):
        """Return a fake job id"""
        return str(uuid4())


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
