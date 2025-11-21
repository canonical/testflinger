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

import json
import tempfile
from unittest.mock import patch
from uuid import uuid4

import pytest

from testflinger_device_connectors.devices.multi.multi import Multi
from testflinger_device_connectors.devices.multi.tfclient import TFClient


class MockTFClient(TFClient):
    """Mock TFClient object."""

    def submit_job(self, job_data):
        """Return a fake job id."""
        return str(uuid4())

    def submit_agent_job(self, job_data):
        """Return a fake agent job id."""
        return self.submit_job(job_data)


def test_bad_tfclient_url():
    """Test that Multi raises an exception when TFClient URL is bad."""
    with pytest.raises(ValueError):
        TFClient(None)
    with pytest.raises(ValueError):
        TFClient("foo.com")


def test_inject_allocate_data():
    """Test that allocate_data section is injected into job."""
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
    """Test that parent_jobid is injected into job."""
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


def test_this_job_completed():
    """Test this_job_completed returns True only when the job is completed."""
    test_config = {"agent_name": "test_agent"}
    job_data = {
        "job_id": "11111111-1111-1111-1111-111111111111",
    }

    # completed state is detected as completed
    completed_client = MockTFClient("http://localhost")
    completed_client.get_status = lambda job_id: "completed"
    test_agent = Multi(test_config, job_data, completed_client)
    assert test_agent.this_job_completed() is True

    # cancelled state is detected as completed
    cancelled_client = MockTFClient("http://localhost")
    cancelled_client.get_status = lambda job_id: "cancelled"
    test_agent = Multi(test_config, job_data, cancelled_client)
    assert test_agent.this_job_completed() is True

    # anything else is not completed
    incomplete_client = MockTFClient("http://localhost")
    incomplete_client.get_status = lambda job_id: "something else"
    test_agent = Multi(test_config, job_data, incomplete_client)
    assert test_agent.this_job_completed() is False


@patch(
    "testflinger_device_connectors.devices.multi.multi.copy_ssh_keys_to_devices"
)
@patch("time.sleep")
def test_multi_reserve(mock_sleep, mock_copy_keys):
    """Test Multi.reserve method functionality."""
    test_config = {"agent_name": "test_agent"}
    job_data = {
        "job_id": "test-job-123",
        "reserve_data": {"ssh_keys": ["key1", "key2"], "timeout": "1800"},
        "test_data": {"test_username": "testuser"},
    }

    # Create job_list.json file with mock data
    job_list = [
        {"device_info": {"device_ip": "192.168.1.1"}},
        {"device_info": {"device_ip": "192.168.1.2"}},
    ]

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as tmp_file:
        json.dump(job_list, tmp_file)

    # Mock builtins.open to return our temp file
    # when job_list.json is requested
    with patch("builtins.open", create=True) as mo:
        mo.return_value.__enter__.return_value.read.return_value = json.dumps(
            job_list
        )

        # Mock print to capture output
        with patch("builtins.print") as mock_print:
            test_agent = Multi(
                test_config, job_data, MockTFClient("http://localhost")
            )
            test_agent.reserve()

    # Verify copy_ssh_keys_to_devices was called with correct parameters
    mock_copy_keys.assert_called_once_with(
        ["key1", "key2"], ["192.168.1.1", "192.168.1.2"], "testuser"
    )

    # Verify time.sleep was called with timeout
    mock_sleep.assert_called_once_with(1800)

    # Verify print statements were made
    assert (
        mock_print.call_count >= 5
    )  # Multiple print statements in reserve method


@patch(
    "testflinger_device_connectors.devices.multi.multi.copy_ssh_keys_to_devices"
)
@patch("time.sleep")
def test_multi_reserve_default_username(mock_sleep, mock_copy_keys):
    """Test Multi.reserve method with default username."""
    test_config = {"agent_name": "test_agent"}
    job_data = {
        "job_id": "test-job-123",
        "reserve_data": {"ssh_keys": ["key1"], "timeout": "3600"},
        # No test_data section - should default to ubuntu
    }

    job_list = [{"device_info": {"device_ip": "192.168.1.1"}}]

    with patch("builtins.open", create=True) as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = (
            json.dumps(job_list)
        )

        with patch("builtins.print"):
            test_agent = Multi(
                test_config, job_data, MockTFClient("http://localhost")
            )
            test_agent.reserve()

    # Verify copy_ssh_keys_to_devices was called
    mock_copy_keys.assert_called_once_with(["key1"], ["192.168.1.1"], "ubuntu")

    # Verify time.sleep was called with timeout
    mock_sleep.assert_called_once_with(3600)


@patch(
    "testflinger_device_connectors.devices.multi.multi.copy_ssh_keys_to_devices"
)
@patch("time.sleep")
def test_multi_reserve_no_ssh_keys(mock_sleep, mock_copy_keys):
    """Test Multi.reserve method with no SSH keys."""
    test_config = {"agent_name": "test_agent"}
    job_data = {
        "job_id": "test-job-123",
        "reserve_data": {
            "timeout": "1800"
            # No ssh_keys provided
        },
        "test_data": {"test_username": "testuser"},
    }

    job_list = [{"device_info": {"device_ip": "192.168.1.1"}}]

    with patch("builtins.open", create=True) as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = (
            json.dumps(job_list)
        )

        with patch("builtins.print"):
            test_agent = Multi(
                test_config, job_data, MockTFClient("http://localhost")
            )
            test_agent.reserve()

    # Verify copy_ssh_keys_to_devices was called with empty list
    mock_copy_keys.assert_called_once_with([], ["192.168.1.1"], "testuser")

    # Verify time.sleep was called with timeout
    mock_sleep.assert_called_once_with(1800)
