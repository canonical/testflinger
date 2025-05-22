# Copyright (C) 2025 Canonical Ltd.
"""Unit tests for Testflinger client module."""

import uuid

import pytest

from testflinger_common.client import Client


class TestClient:
    @pytest.fixture
    def client(self):
        """Fixture for Testflinger client."""
        server = "http://127.0.0.1:8000"
        client_id = "client id"
        client_secret = "client secret"
        yield Client(
            server=server, client_id=client_id, client_secret=client_secret
        )

    def test_post_job_status_update(self, client, requests_mock):
        """Test sending status updates with valid webhook."""
        webhook = "http://foo"
        job_id = str(uuid.uuid1())
        requests_mock.post(
            f"{client.server}/v1/job/{job_id}/events", json={}, status_code=200
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
        client.post_job_status_update(
            "queue", "agent", webhook, job_id, events
        )
        expected_json = {
            "agent_id": "agent",
            "job_queue": "queue",
            "job_status_webhook": webhook,
            "events": events,
        }
        assert requests_mock.last_request.json() == expected_json

    def test_post_job_status_update_no_webhook(self, client, requests_mock):
        """Test sending status update with no webhook fails."""
        webhook = ""
        job_id = str(uuid.uuid1())
        requests_mock.post(
            f"{client.server}/v1/job/{job_id}/events", status_code=200
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
        with pytest.raises(ValueError):
            client.post_job_status_update(
                "queue", "agent", webhook, job_id, events
            )

    def test_get_job_attachments(self, client, requests_mock, tmp_path):
        """Test getting attachments."""
        job_id = str(uuid.uuid1())
        attachments_dir = tmp_path / "attachments.tar.gz"
        requests_mock.get(
            f"{client.server}/v1/job/{job_id}/attachments",
            status_code=200,
        )
        client.get_job_attachments(job_id, attachments_dir)
        assert requests_mock.called
        assert attachments_dir.is_file()

    def test_get_job_artifacts(self, client, requests_mock, tmp_path):
        """Test getting artifacts."""
        job_id = str(uuid.uuid1())
        tarball = tmp_path / "artifacts.tar.gz"
        requests_mock.get(
            f"{client.server}/v1/result/{job_id}/artifact",
            status_code=200,
        )
        client.get_job_artifacts(job_id, tarball)
        assert requests_mock.called
        assert tarball.is_file()
