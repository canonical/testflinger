# Copyright (C) 2016 Canonical
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

import json
import pytest
import uuid

import requests_mock as rmock

from testflinger_agent.client import TestflingerClient as _TestflingerClient


class TestClient:
    @pytest.fixture
    def client(self):
        config = {
            "agent_id": "test_agent",
            "server_address": "127.0.0.1:8000",
            "advertised_queues": {"test_queue": "test_queue"},
            "advertised_images": {
                "test_queue": {"test_image": "url: http://foo"}
            },
        }
        yield _TestflingerClient(config)

    def test_check_jobs_empty(self, client, requests_mock):
        requests_mock.get(rmock.ANY, status_code=200)
        job_data = client.check_jobs()
        assert job_data is None

    def test_check_jobs_with_job(self, client, requests_mock):
        fake_job_data = {
            "job_id": str(uuid.uuid1()),
            "job_queue": "test_queue",
        }
        requests_mock.get(rmock.ANY, json=fake_job_data)
        job_data = client.check_jobs()
        assert job_data == fake_job_data

    def test_post_advertised_queues(self, client, requests_mock):
        """
        ensure that the server api /v1/agents/queues was called with
        the correct queue data
        """
        requests_mock.post(rmock.ANY, status_code=200)
        client.post_advertised_queues()
        assert requests_mock.last_request.json() == {
            "test_queue": "test_queue"
        }

    def test_post_advertised_images(self, client, requests_mock):
        """
        ensure that the server api /v1/agents/images was called with
        the correct image data
        """
        requests_mock.post(rmock.ANY, status_code=200)
        client.post_advertised_images()
        assert requests_mock.last_request.json() == {
            "test_queue": {"test_image": "url: http://foo"}
        }

    def test_post_provision_logs(self, client, requests_mock):
        """Test that /v1/agents/provision_logs is called with the right data"""
        job_id = "00000000-0000-0000-0000-00000000000"
        exit_code = 1
        detail = "provision_failed"
        requests_mock.post(
            "http://127.0.0.1:8000/v1/agents/provision_logs/"
            f"{client.config['agent_id']}",
            status_code=200,
        )
        client.post_provision_log(job_id, exit_code, detail)
        last_request = requests_mock.last_request.json()
        assert last_request["job_id"] == job_id
        assert last_request["exit_code"] == exit_code
        assert last_request["detail"] == detail

    def test_transmit_job_outcome(self, client, requests_mock, tmp_path):
        """
        Test that transmit_job_outcome sends results to the server
        """
        job_id = str(uuid.uuid1())
        testflinger_data = {"job_id": job_id}
        testflinger_json = tmp_path / "testflinger.json"
        testflinger_json.write_text(json.dumps(testflinger_data))
        testflinger_outcome_json = tmp_path / "testflinger-outcome.json"
        testflinger_outcome_json.write_text("{}")
        requests_mock.post(
            f"http://127.0.0.1:8000/v1/result/{job_id}", status_code=200
        )
        client.transmit_job_outcome(tmp_path)
        assert requests_mock.last_request.json() == {"job_state": "complete"}

    def test_transmit_job_artifact(self, client, requests_mock, tmp_path):
        """
        Test that transmit_job_outcome sends artifacts if they exist
        """
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()
        job_id = str(uuid.uuid1())
        testflinger_data = {"job_id": job_id}
        testflinger_json = tmp_path / "testflinger.json"
        testflinger_json.write_text(json.dumps(testflinger_data))
        requests_mock.post(
            f"http://127.0.0.1:8000/v1/result/{job_id}/artifact",
            status_code=200,
        )
        client.transmit_job_outcome(tmp_path)
        assert requests_mock.called

    def test_transmit_job_outcome_missing_json(self, client, tmp_path, caplog):
        """
        Test that transmit_job_outcome logs an error and exits if
        testflinger.json is missing
        """
        client.transmit_job_outcome(tmp_path)
        assert "Unable to read job ID" in caplog.text
