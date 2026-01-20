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
import uuid
from http import HTTPStatus
from unittest.mock import patch

import pytest
import requests_mock as rmock
from requests.exceptions import RequestException

from testflinger_agent.client import TestflingerClient as _TestflingerClient
from testflinger_agent.errors import TFServerError


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
        requests_mock.get(rmock.ANY, status_code=HTTPStatus.OK)
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

    def test_check_jobs_with_restricted_queues(self, client, requests_mock):
        restricted_data = {
            "restricted_to": {
                "test_queue": ["test-client-id"],
            }
        }
        requests_mock.get(
            "http://127.0.0.1:8000/v1/agents/data/test_agent",
            json=restricted_data,
        )
        fake_job_data = {
            "job_id": str(uuid.uuid1()),
            "job_queue": "test_queue",
        }
        requests_mock.get(
            "http://127.0.0.1:8000/v1/job",
            json=fake_job_data,
        )
        job_data = client.check_jobs()
        params = requests_mock.last_request.qs.get("queue")
        assert params == ["test_queue"]
        assert job_data == fake_job_data

    def test_check_jobs_with_unrestricted_queues(self, client, requests_mock):
        client.config["job_queues"] = ["queue1"]
        unrestricted_data = {"restricted_to": {}}
        requests_mock.get(
            "http://127.0.0.1:8000/v1/agents/data/test_agent",
            json=unrestricted_data,
        )
        fake_job_data = {
            "job_id": str(uuid.uuid1()),
            "job_queue": "queue1",
        }
        requests_mock.get(
            "http://127.0.0.1:8000/v1/job",
            json=fake_job_data,
        )
        job_data = client.check_jobs()
        params = requests_mock.last_request.qs.get("queue")
        assert params == ["queue1"]
        assert job_data == fake_job_data

    def test_post_advertised_queues(self, client, requests_mock):
        """
        Ensure that the server api /v1/agents/queues was called with
        the correct queue data.
        """
        requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)
        client.post_advertised_queues()
        assert requests_mock.last_request.json() == {
            "test_queue": "test_queue"
        }

    def test_post_advertised_images(self, client, requests_mock):
        """
        Ensure that the server api /v1/agents/images was called with
        the correct image data.
        """
        requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)
        client.post_advertised_images()
        assert requests_mock.last_request.json() == {
            "test_queue": {"test_image": "url: http://foo"}
        }

    def test_post_provision_logs(self, client, requests_mock):
        """Test that /v1/agents/provision_logs is called
        with the right data.
        """
        job_id = "00000000-0000-0000-0000-00000000000"
        exit_code = 1
        detail = "provision_failed"
        requests_mock.post(
            "http://127.0.0.1:8000/v1/agents/provision_logs/"
            f"{client.config['agent_id']}",
            status_code=HTTPStatus.OK,
        )
        client.post_provision_log(job_id, exit_code, detail)
        last_request = requests_mock.last_request.json()
        assert last_request["job_id"] == job_id
        assert last_request["exit_code"] == exit_code
        assert last_request["detail"] == detail

    def test_transmit_job_outcome(self, client, requests_mock, tmp_path):
        """Test that transmit_job_outcome sends results to the server."""
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

    def test_transmit_job_outcome_with_error(
        self, client, requests_mock, tmp_path, caplog
    ):
        """
        Test that OSError during save_artifacts results in removing the job
        directory and logging an error so that we don't crash and keep
        filling up the disk.
        """
        job_id = str(uuid.uuid1())
        testflinger_data = {"job_id": job_id}
        testflinger_json = tmp_path / "testflinger.json"
        testflinger_json.write_text(json.dumps(testflinger_data))
        testflinger_outcome_json = tmp_path / "testflinger-outcome.json"
        testflinger_outcome_json.write_text("{}")
        requests_mock.post(
            f"http://127.0.0.1:8000/v1/result/{job_id}",
            status_code=HTTPStatus.OK,
        )

        # Simulate an error during save_artifacts
        with patch.object(client, "save_artifacts", side_effect=OSError):
            client.transmit_job_outcome(tmp_path)
        assert tmp_path.exists() is False
        assert "Unable to save artifacts" in caplog.text

    def test_result_post_endpoint_error(self, client, requests_mock, caplog):
        """
        Test that the client handles the case where the server returns
        an error status code for the results post endpoint.
        """
        job_id = str(uuid.uuid1())
        requests_mock.post(
            f"http://127.0.0.1:8000/v1/result/{job_id}",
            status_code=HTTPStatus.NOT_FOUND,
        )
        with pytest.raises(TFServerError):
            client.post_result(job_id, {})
            assert "Unable to post results" in caplog.text

    def test_result_get_endpoint_error(self, client, requests_mock, caplog):
        """
        Test that the client handles the case where the server returns
        an error status code for the results get endpoint.
        """
        job_id = str(uuid.uuid1())
        requests_mock.get(
            f"http://127.0.0.1:8000/v1/result/{job_id}",
            status_code=HTTPStatus.NOT_FOUND,
        )
        response = client.get_result(job_id)
        assert response == {}
        assert "Unable to get results" in caplog.text

    def test_attachment_endpoint_error(self, client, requests_mock, caplog):
        """
        Test that the client handles the case where the server returns
        an error status code for the attachment endpoint.
        """
        job_id = str(uuid.uuid1())
        requests_mock.get(
            f"http://127.0.0.1:8000/v1/job/{job_id}/attachments",
            status_code=HTTPStatus.NOT_FOUND,
        )

        with pytest.raises(TFServerError):
            client.get_attachments(job_id, None)
            assert "Unable to retrieve attachments for job" in caplog.text

    def test_transmit_job_artifact(self, client, requests_mock, tmp_path):
        """Test that transmit_job_outcome sends artifacts if they exist."""
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
        testflinger.json is missing.
        """
        client.transmit_job_outcome(tmp_path)
        assert "Unable to read job ID" in caplog.text

    def test_post_status_update(self, client, requests_mock):
        """
        Test that the agent sends a status update to the status endpoint
        if there is a valid webhook.
        """
        webhook = "http://foo"
        job_id = str(uuid.uuid1())
        requests_mock.post(
            f"http://127.0.0.1:8000/v1/job/{job_id}/events",
            status_code=HTTPStatus.OK,
        )
        events = [
            {
                "event_name": "provision_start",
                "timestamp": "2014-12-22T03:12:58.019077+00:00",
                "detail": "",
            },
            {
                "event_name": "provision_success",
                "timestamp": "2014-12-22T03:12:58.019077+00:00",
                "detail": "",
            },
        ]
        client.post_status_update("myjobqueue", webhook, events, job_id)
        expected_json = {
            "agent_id": client.config.get("agent_id"),
            "job_queue": "myjobqueue",
            "job_status_webhook": webhook,
            "events": events,
        }
        assert requests_mock.last_request.json() == expected_json

    def test_status_update_endpoint_error(self, client, requests_mock, caplog):
        """
        Test that the client handles the case where the server returns
        an error status code for the status_update endpoint.
        """
        job_id = str(uuid.uuid1())
        requests_mock.post(
            f"http://127.0.0.1:8000/v1/job/{job_id}/events",
            status_code=HTTPStatus.NOT_FOUND,
        )
        client.post_status_update("", "", [], job_id)
        assert "Unable to post status updates" in caplog.text

    def test_get_agent_data(self, client, requests_mock):
        agent_data = {
            "agent_id": "test_agent",
            "queues": ["queue1", "queue2"],
            "restricted_to": {"queue1": ["client1"]},
        }
        requests_mock.get(
            "http://127.0.0.1:8000/v1/agents/data/test_agent",
            json=agent_data,
        )

        data = client.get_agent_data("test_agent")
        assert data == agent_data

    def test_agent_registration_and_cookie_workflow(
        self, client, requests_mock
    ):
        """Test agent registration and cookie workflow."""
        # Step 1: Agent registers with server
        agent_data = {
            "state": "waiting",
            "queues": ["test_queue"],
            "location": "here",
        }
        requests_mock.post(
            "http://127.0.0.1:8000/v1/agents/data/test_agent",
            status_code=HTTPStatus.OK,
            headers={
                "Set-Cookie": (
                    "agent_name=test_agent; HttpOnly; SameSite=Strict"
                )
            },
        )
        # Registration call (from _post_initial_agent_data in agent.py)
        client.post_agent_data(agent_data)
        assert requests_mock.called

        # Step 2: Agent requests a job and should include the cookie
        fake_job_data = {
            "job_id": str(uuid.uuid1()),
            "job_queue": "test_queue",
            "exclude_agents": [],
        }
        requests_mock.get(
            "http://127.0.0.1:8000/v1/agents/data/test_agent",
            json={},  # "restricted_to": {}},
        )
        requests_mock.get(
            "http://127.0.0.1:8000/v1/job",
            json=fake_job_data,
            headers={
                "Set-Cookie": (
                    "agent_name=test_agent; HttpOnly; SameSite=Strict"
                )
            },
        )

        # Session should automatically handle cookies after first response
        # The session persists cookies across requests
        job_data = client.check_jobs()
        assert job_data == fake_job_data

        # Verify the session made the request (session handles cookies)
        assert requests_mock.last_request.method == "GET"
        assert "/v1/job" in requests_mock.last_request.url

    def test_check_jobs_without_agent_registration_reregisters(
        self, client, requests_mock
    ):
        """
        Test that check_jobs handles 401 (no agent_name cookie) by
        re-registering the agent and returning None.
        """
        requests_mock.get(
            "http://127.0.0.1:8000/v1/agents/data/test_agent",
            json={"restricted_to": {}},
        )
        requests_mock.get(
            "http://127.0.0.1:8000/v1/job",
            status_code=HTTPStatus.UNAUTHORIZED,
            json={"message": "Agent not identified"},
        )
        requests_mock.post(
            "http://127.0.0.1:8000/v1/agents/data/test_agent",
            status_code=HTTPStatus.OK,
        )

        # check_jobs should handle 401 by re-registering and returning None
        result = client.check_jobs()
        assert result is None

        # Verify that post_agent_data was called for re-registration, i.e.
        # the POST /agents/data/<agent_name> endpoint was called, once.
        post_requests = [
            req
            for req in requests_mock.request_history
            if req.method == "POST"
        ]
        assert len(post_requests) == 1
        assert post_requests[0].json() == {"job_id": ""}

    def test_check_jobs_request_exception(self, client):
        """
        Test that check_jobs handles RequestException (network failure)
        by logging error and sleeping.
        """
        network_error = RequestException("Connection refused")

        with patch.object(client.session, "get", side_effect=network_error):
            with patch("testflinger_agent.client.logger") as mock_logger:
                with patch(
                    "testflinger_agent.client.time.sleep"
                ) as mock_sleep:
                    result = client.check_jobs()

        # Verify logger.error was called with the exception
        mock_logger.error.assert_called_with(network_error)
        # Verify time.sleep(60) was called
        mock_sleep.assert_called_with(60)
        # Verify None is returned (no job available after network error)
        assert result is None
