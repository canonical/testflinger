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
from testflinger_agent.errors import InvalidTokenError, TFServerError


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
        requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)
        job_data = client.check_jobs()
        assert job_data is None

    def test_check_jobs_with_job(self, client, requests_mock):
        fake_job_data = {
            "job_id": str(uuid.uuid1()),
            "job_queue": "test_queue",
        }
        requests_mock.get(rmock.ANY, json=fake_job_data)
        requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)
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
        requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)
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
        requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)
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
            f"http://127.0.0.1:8000/v1/result/{job_id}",
            status_code=HTTPStatus.OK,
        )
        client.transmit_job_outcome(tmp_path)
        assert requests_mock.last_request.json() == {"job_state": "complete"}

    @patch.object(_TestflingerClient, "save_artifacts", side_effect=OSError)
    def test_transmit_job_outcome_with_error(
        self, mock_save_artifacts, client, requests_mock, tmp_path, caplog
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
        assert "error: 404" in caplog.text

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
        assert "error: 404" in caplog.text

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
            status_code=HTTPStatus.OK,
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

    @patch("testflinger_agent.client.time.sleep")
    @patch("testflinger_agent.client.logger")
    @patch("requests.Session.get")
    def test_check_jobs_request_exception(
        self, mock_get, mock_logger, mock_sleep, client
    ):
        """
        Test that check_jobs handles RequestException (network failure)
        by logging error and sleeping.
        """
        network_error = RequestException("Connection refused")
        mock_get.side_effect = network_error

        result = client.check_jobs()

        # Verify logger.error was called with the exception
        mock_logger.error.assert_called_with(network_error)
        # Verify time.sleep(60) was called
        mock_sleep.assert_called_with(60)
        # Verify None is returned (no job available after network error)
        assert result is None

    def test_missing_token_file(self, client, requests_mock):
        """Test that agent handles missing token file gracefully."""
        client.config["token_file"] = "/wrong/path/token"  # noqa: S105
        requests_mock.get(rmock.ANY, status_code=HTTPStatus.OK)
        requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)

        # Should return None and not raise an exception
        result = client.check_jobs()
        assert result is None

    def test_get_job_fails_token_invalid(
        self, client, requests_mock, tmp_path
    ):
        """Test no job is returned if refresh token is invalid."""
        # Create a token file with an invalid refresh token
        token_file = tmp_path / "refresh_token"
        token_file.write_text(
            json.dumps({"refresh_token": "invalid-token"})  # noqa: S106
        )
        client.config["token_file"] = str(token_file)

        # Mock the refresh endpoint to return BAD_REQUEST for invalid token
        requests_mock.post(
            f"{client.server}/v1/oauth2/refresh",
            status_code=HTTPStatus.BAD_REQUEST,
            json={"message": "Invalid refresh token."},
        )
        requests_mock.get(rmock.ANY, status_code=HTTPStatus.OK)

        result = client.check_jobs()
        assert result is None

    def test_get_job_success_on_valid_token(
        self, client, requests_mock, tmp_path
    ):
        """Test that job data is returned on valid token."""
        # Create a valid token file
        token_file = tmp_path / "refresh_token"
        token_file.write_text(json.dumps({"refresh_token": "valid-token"}))
        client.config["token_file"] = str(token_file)

        # Mock refresh endpoint to return valid access token
        fake_access_token = "valid-access-token"  # noqa: S105
        requests_mock.post(
            f"{client.server}/v1/oauth2/refresh",
            json={"access_token": fake_access_token},
        )
        # Mock post agent data endpoint for retrieving session cookie
        requests_mock.post(
            f"{client.server}/v1/agents/data/test_agent",
            json={"job_id": ""},
        )
        # Mock agent data endpoint
        requests_mock.get(
            f"{client.server}/v1/agents/data/test_agent",
            json={"restricted_to": {}},
        )
        # Mock job endpoint with job data
        fake_job_data = {
            "job_id": str(uuid.uuid1()),
            "job_queue": "test_queue",
        }
        requests_mock.get(
            f"{client.server}/v1/job",
            json=fake_job_data,
        )

        result = client.check_jobs()
        assert result == fake_job_data

        # Verify Authorization header was set
        job_request = [
            r for r in requests_mock.request_history if "/v1/job" in r.url
        ][0]
        auth_header = job_request.headers.get("Authorization")
        assert auth_header == f"Bearer {fake_access_token}"

    def test_get_job_incorrect_role(self, client, requests_mock, tmp_path):
        """Test that no job is returned if access token has incorrect role."""
        # Create a valid token file
        token_file = tmp_path / "token"
        token_file.write_text(json.dumps({"refresh_token": "valid-token"}))
        client.config["token_file"] = str(token_file)

        # Mock refresh endpoint to return valid access token
        requests_mock.post(
            f"{client.server}/v1/oauth2/refresh",
            json={"access_token": "test-access-token"},
        )
        # Mock post agent data endpoint for retrieving session cookie
        requests_mock.post(
            f"{client.server}/v1/agents/data/test_agent",
            json={"job_id": ""},
        )
        # Mock agent data endpoint
        requests_mock.get(
            f"{client.server}/v1/agents/data/test_agent",
            json={"restricted_to": {}},
        )
        # Mock job endpoint to return forbidden due to incorrect role
        requests_mock.get(
            f"{client.server}/v1/job",
            status_code=HTTPStatus.FORBIDDEN,
            json={"message": "Specified action requires role: agent"},
        )

        result = client.check_jobs()
        assert result is None

    def test_malformed_token_file(self, client, requests_mock, tmp_path):
        """Test that agent handles malformed JSON in token file gracefully."""
        token_file = tmp_path / "refresh_token"
        token_file.write_text("not valid json{{{")
        client.config["token_file"] = str(token_file)

        requests_mock.get(rmock.ANY, status_code=HTTPStatus.OK)
        requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)

        # Should return None and not raise an exception
        result = client.check_jobs()
        assert result is None

    def test_get_access_token_raises_on_bad_request(
        self, client, requests_mock, tmp_path
    ):
        """Test that get_access_token raises InvalidTokenError on 400 error."""
        token_file = tmp_path / "refresh_token"
        token_file.write_text(json.dumps({"refresh_token": "invalid-token"}))
        client.config["token_file"] = str(token_file)

        # Mock the refresh endpoint to return BAD_REQUEST
        requests_mock.post(
            f"{client.server}/v1/oauth2/refresh",
            status_code=HTTPStatus.BAD_REQUEST,
            json={"message": "Invalid refresh token."},
        )

        with pytest.raises(InvalidTokenError):
            client.get_access_token()

    def test_get_access_token_returns_none_on_server_error(
        self, client, requests_mock, tmp_path
    ):
        """Test that a non-400 HTTP error returns None."""
        token_file = tmp_path / "refresh_token"
        token_file.write_text(json.dumps({"refresh_token": "valid-token"}))
        client.config["token_file"] = str(token_file)

        requests_mock.post(
            f"{client.server}/v1/oauth2/refresh",
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        )

        result = client.get_access_token()
        assert result is None

    def test_get_access_token_refresh_network_error(
        self, client, requests_mock, tmp_path, caplog
    ):
        """Test that a network error during token refresh is handled."""
        token_file = tmp_path / "refresh_token"
        token_file.write_text(json.dumps({"refresh_token": "valid-token"}))
        client.config["token_file"] = str(token_file)

        # Mock the refresh endpoint to raise a connection error
        requests_mock.post(
            f"{client.server}/v1/oauth2/refresh",
            exc=RequestException("Connection refused"),
        )
        requests_mock.get(rmock.ANY, status_code=HTTPStatus.OK)
        requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)

        result = client.check_jobs()
        assert result is None
        assert "Failed to refresh access token" in caplog.text

    def test_get_job_missing_token_header(self, client, requests_mock):
        """Test no job is returned if access token is missing from header."""
        # No token file configured, so no Authorization header will be set
        client.config["token_file"] = None

        # Mock agent data endpoint
        requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)
        requests_mock.get(
            f"{client.server}/v1/agents/data/test_agent",
            json={"restricted_to": {}},
        )
        # Mock job endpoint to return as no access token provided in header
        requests_mock.get(
            f"{client.server}/v1/job",
            status_code=HTTPStatus.UNAUTHORIZED,
            json={
                "message": "Authentication is required for specified endpoint"
            },
        )

        result = client.check_jobs()
        assert result is None

    def test_update_session_auth_headers(
        self, client, requests_mock, tmp_path
    ):
        """Test authentication headers gets updated on new access token."""
        # Create a valid token file
        token_file = tmp_path / "refresh_token"
        token_file.write_text(json.dumps({"refresh_token": "valid-token"}))
        client.config["token_file"] = str(token_file)

        first_access_token = "access-token-1"  # noqa: S105
        second_access_token = "access-token-2"  # noqa: S105

        # Mock refresh endpoint to return different tokens on each call
        requests_mock.post(
            f"{client.server}/v1/oauth2/refresh",
            [
                {"json": {"access_token": first_access_token}},
                {"json": {"access_token": second_access_token}},
            ],
        )
        # Mock post agent data endpoint for retrieving session cookie
        requests_mock.post(
            f"{client.server}/v1/agents/data/test_agent",
            json={"job_id": ""},
        )
        # Mock agent data endpoint
        requests_mock.get(
            f"{client.server}/v1/agents/data/test_agent",
            json={"restricted_to": {}},
        )
        # Mock job endpoint
        requests_mock.get(
            f"{client.server}/v1/job",
            json={},
        )

        # First call should set the header with the first access token
        client.check_jobs()
        assert (
            client.session.headers["Authorization"]
            == f"Bearer {first_access_token}"
        )

        # Second call should update the header with the new access token
        client.check_jobs()
        assert (
            client.session.headers["Authorization"]
            == f"Bearer {second_access_token}"
        )

    def test_update_session_auth_refreshes_cookies(
        self, client, requests_mock, tmp_path
    ):
        """Test session cookies are refreshed when empty."""
        token_file = tmp_path / "refresh_token"
        token_file.write_text(json.dumps({"refresh_token": "valid-token"}))
        client.config["token_file"] = str(token_file)

        requests_mock.post(
            f"{client.server}/v1/oauth2/refresh",
            json={"access_token": "test-token"},  # noqa: S106
        )
        requests_mock.post(
            f"{client.server}/v1/agents/data/test_agent",
            json={"job_id": ""},
        )

        # Cookies are empty, so post_agent_data should be called
        assert not client.session.cookies
        client._update_session_auth()

        # Verify the post to agent data was made for cookie refresh
        agent_data_calls = [
            request
            for request in requests_mock.request_history
            if request.method == "POST"
            and "/v1/agents/data/test_agent" in request.url
        ]
        assert len(agent_data_calls) == 1

    def test_update_session_auth_skips_cookie_refresh(
        self, client, requests_mock, tmp_path
    ):
        """Test session skips cookie refresh when cookies already exist."""
        token_file = tmp_path / "refresh_token"
        token_file.write_text(json.dumps({"refresh_token": "valid-token"}))
        client.config["token_file"] = str(token_file)

        requests_mock.post(
            f"{client.server}/v1/oauth2/refresh",
            json={"access_token": "test-token"},  # noqa: S106
        )

        # Pre-populate session cookies so post_agent_data is skipped
        client.session.cookies.set("session", "existing-cookie")
        client._update_session_auth()

        # Verify no post to agent data was made
        agent_data_calls = [
            request
            for request in requests_mock.request_history
            if request.method == "POST"
            and "/v1/agents/data/test_agent" in request.url
        ]
        assert len(agent_data_calls) == 0

    @patch("requests.Session.post", return_value=None)
    def test_post_status_update_none_response(self, mock_post, client, caplog):
        """
        Test that post_status_update handles None response gracefully.
        This simulates the case where retry exhaustion returns None.
        """
        job_id = str(uuid.uuid1())

        client.post_status_update("myjobqueue", "http://foo", [], job_id)
        assert "No response received" in caplog.text

    @patch("requests.Session.post", return_value=None)
    def test_post_result_none_response(self, mock_post, client, caplog):
        """Test that post_result handles None response gracefully."""
        job_id = str(uuid.uuid1())

        with pytest.raises(TFServerError, match="No response received"):
            client.post_result(job_id, {"test": "data"})
        assert "No response received" in caplog.text

    @patch("requests.Session.get", return_value=None)
    def test_get_result_none_response(self, mock_get, client, caplog):
        """Test that get_result handles None response gracefully."""
        job_id = str(uuid.uuid1())

        result = client.get_result(job_id)
        assert result == {}
        assert "No response received" in caplog.text

    def test_save_artifacts_error_response(
        self, client, requests_mock, tmp_path, caplog
    ):
        """Test that save_artifacts handles HTTP error response correctly."""
        job_id = str(uuid.uuid1())

        # Create artifacts directory with a file
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()
        (artifacts_dir / "test.txt").write_text("test content")

        artifact_uri = f"http://127.0.0.1:8000/v1/result/{job_id}/artifact"
        requests_mock.post(artifact_uri, status_code=500)
        with pytest.raises(TFServerError):
            client.save_artifacts(tmp_path, job_id)
        assert "Unable to post results" in caplog.text
        assert "error: 500" in caplog.text

    @patch("requests.Session.post", return_value=None)
    def test_save_artifacts_none_response(
        self, mock_post, client, tmp_path, caplog
    ):
        """Test that save_artifacts handles None response gracefully."""
        job_id = str(uuid.uuid1())

        # Create artifacts directory with a file
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()
        (artifacts_dir / "test.txt").write_text("test content")

        with pytest.raises(TFServerError, match="No response received"):
            client.save_artifacts(tmp_path, job_id)
        assert "No response received" in caplog.text
