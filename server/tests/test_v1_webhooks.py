# Copyright (C) 2025 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Tests for forwarding status updates to the supported webhook types."""

from http import HTTPStatus

import pytest
import requests

from testflinger.api import webhooks

MATTERMOST_URL = "https://chat.canonical.com/hooks/hash-hooks"
DEFAULT_WEBHOOK_URL = (
    "http://mywebhook.local/v1/test-executions/1234/status_update"
)

STATUS_UPDATE_EVENTS = [
    {
        "event_name": "provision_start",
        "timestamp": "2014-12-22T03:12:58.019077+00:00",
        "detail": "provisioning",
    },
    {
        "event_name": "job_end",
        "timestamp": "2014-12-22T03:14:58.019077+00:00",
        "detail": "normal_exit",
    },
]


def status_update(webhook_definitions, events=None):
    """Build the status update an agent posts to the events endpoint."""
    return {
        "agent_id": "agent1",
        "job_queue": "myjobqueue",
        "job_status_webhooks": webhook_definitions,
        "events": STATUS_UPDATE_EVENTS if events is None else events,
    }


@pytest.mark.parametrize(
    "url,expected",
    (
        (MATTERMOST_URL, webhooks.WebhookType.MATTERMOST),
        (
            "https://chat.canonical.com/hooks/another-hook",
            webhooks.WebhookType.MATTERMOST,
        ),
        # a /hooks/ path on an unrelated host is not a Mattermost webhook
        (
            "https://elsewhere.example.com/hooks/abcdef",
            webhooks.WebhookType.DEFAULT_WEBHOOK,
        ),
        # the prefix has to match in full, scheme included
        (
            "http://chat.canonical.com/hooks/abcdef",
            webhooks.WebhookType.DEFAULT_WEBHOOK,
        ),
        (
            "https://chat.canonical.com/api/v4/teams",
            webhooks.WebhookType.DEFAULT_WEBHOOK,
        ),
        (DEFAULT_WEBHOOK_URL, webhooks.WebhookType.DEFAULT_WEBHOOK),
        (
            "http://another-webhook.local/",
            webhooks.WebhookType.DEFAULT_WEBHOOK,
        ),
    ),
)
def test_detect_webhook_type(url, expected):
    """Test that the webhook type is inferred from the URL."""
    assert webhooks.detect_webhook_type(url) is expected


def test_mattermost_type_can_be_requested_explicitly():
    """Test that an unrecognised URL can still be typed by the job."""
    spec = webhooks.WebhookSpec.from_definition(
        {"url": "https://mattermost.example.com/hooks/abcdef"}
    )
    assert spec.type is webhooks.WebhookType.DEFAULT_WEBHOOK

    spec = webhooks.WebhookSpec.from_definition(
        {
            "url": "https://mattermost.example.com/hooks/abcdef",
            "type": "mattermost",
        }
    )
    assert spec.type is webhooks.WebhookType.MATTERMOST


def test_webhook_spec_from_url_string():
    """Test that a plain URL gets its type inferred."""
    spec = webhooks.WebhookSpec.from_definition(MATTERMOST_URL)
    assert spec.url == MATTERMOST_URL
    assert spec.type is webhooks.WebhookType.MATTERMOST


def test_webhook_spec_from_object_overrides_detection():
    """Test that an explicit type takes precedence over detection."""
    spec = webhooks.WebhookSpec.from_definition(
        {
            "url": DEFAULT_WEBHOOK_URL,
            "type": "mattermost",
        }
    )
    assert spec.type is webhooks.WebhookType.MATTERMOST


def test_webhook_spec_rejects_unknown_type():
    """Test that an unknown webhook type is rejected."""
    with pytest.raises(ValueError):
        webhooks.WebhookSpec.from_definition(
            {"url": DEFAULT_WEBHOOK_URL, "type": "carrier-pigeon"}
        )


def test_mattermost_request_carries_no_authorization():
    """Test that Mattermost requests are never given a credential."""
    spec = webhooks.WebhookSpec.from_definition(MATTERMOST_URL)
    request = webhooks.build_request(
        spec,
        status_update(MATTERMOST_URL),
        "my-job-id",
        job_url="http://testflinger.local/jobs/my-job-id",
        auth_headers={"Authorization": "server-credential"},
    )

    assert request.method == "POST"
    assert "Authorization" not in request.headers
    # only the most recent event is reported
    assert "job_end" in request.json["text"]
    assert "provision_start" not in request.json["text"]
    assert "normal_exit" in request.json["text"]
    assert "myjobqueue" in request.json["text"]
    assert "agent1" in request.json["text"]
    assert "my-job-id" in request.json["text"]


def test_build_request_rejects_unsupported_type(monkeypatch):
    """Test that a type without a request builder is reported as an error."""
    spec = webhooks.WebhookSpec.from_definition(MATTERMOST_URL)
    monkeypatch.setattr(webhooks, "_REQUEST_BUILDERS", {})

    with pytest.raises(webhooks.WebhookError):
        webhooks.build_request(spec, status_update(MATTERMOST_URL), "job-id")


def test_default_webhook_request_is_forwarded_verbatim():
    """Test that the default webhook keeps receiving the raw status update."""
    spec = webhooks.WebhookSpec.from_definition(DEFAULT_WEBHOOK_URL)
    update = status_update(DEFAULT_WEBHOOK_URL)
    request = webhooks.build_request(
        spec, update, "my-job-id", auth_headers={"Authorization": "credential"}
    )

    assert request.method == "PUT"
    assert request.json is update
    assert request.headers["Authorization"] == "credential"


def test_mattermost_webhook_delivery(
    mongo_app, requests_mock, monkeypatch, agent_auth_header
):
    """Test that a Mattermost webhook receives a POST without credentials."""
    app, _ = mongo_app
    monkeypatch.setenv("WEBHOOK_URLS", "https://chat.canonical.com/")
    monkeypatch.setenv("WEBHOOK_AUTH", "server-credential")
    requests_mock.post(MATTERMOST_URL, status_code=HTTPStatus.OK)

    job_output = app.post(
        "/v1/job",
        json={"job_queue": "test", "job_status_webhook": MATTERMOST_URL},
    )
    assert job_output.status_code == HTTPStatus.OK
    job_id = job_output.json["job_id"]

    output = app.post(
        f"/v1/job/{job_id}/events",
        json=status_update(MATTERMOST_URL),
        headers=agent_auth_header,
    )

    assert output.status_code == HTTPStatus.OK
    assert requests_mock.last_request.method == "POST"
    assert "Authorization" not in requests_mock.last_request.headers
    assert "job_end" in requests_mock.last_request.json()["text"]


def test_webhook_failure_is_isolated(
    mongo_app, requests_mock, monkeypatch, agent_auth_header
):
    """Test that one failing webhook does not stop the others."""
    app, _ = mongo_app
    monkeypatch.setenv(
        "WEBHOOK_URLS",
        "https://chat.canonical.com/, http://mywebhook.local/",
    )
    requests_mock.post(MATTERMOST_URL, exc=requests.exceptions.ConnectionError)
    requests_mock.put(DEFAULT_WEBHOOK_URL, status_code=HTTPStatus.OK)

    job_output = app.post("/v1/job", json={"job_queue": "test"})
    job_id = job_output.json["job_id"]

    output = app.post(
        f"/v1/job/{job_id}/events",
        json=status_update([MATTERMOST_URL, DEFAULT_WEBHOOK_URL]),
        headers=agent_auth_header,
    )

    assert output.status_code == HTTPStatus.OK
    assert requests_mock.last_request.url == DEFAULT_WEBHOOK_URL


def test_webhook_failure_reported_when_all_fail(
    mongo_app, requests_mock, monkeypatch, agent_auth_header
):
    """Test that the request fails if every webhook failed."""
    app, _ = mongo_app
    monkeypatch.setenv(
        "WEBHOOK_URLS",
        "https://chat.canonical.com/, http://mywebhook.local/",
    )
    requests_mock.post(MATTERMOST_URL, exc=requests.exceptions.ConnectionError)
    requests_mock.put(DEFAULT_WEBHOOK_URL, exc=requests.exceptions.Timeout)

    job_output = app.post("/v1/job", json={"job_queue": "test"})
    job_id = job_output.json["job_id"]

    output = app.post(
        f"/v1/job/{job_id}/events",
        json=status_update([MATTERMOST_URL, DEFAULT_WEBHOOK_URL]),
        headers=agent_auth_header,
    )

    assert output.status_code == HTTPStatus.BAD_GATEWAY


def test_job_post_with_webhook_object(mongo_app):
    """Test that a webhook object is accepted and stored as given."""
    app, _ = mongo_app
    webhook = {"url": MATTERMOST_URL, "type": "mattermost"}
    job_output = app.post(
        "/v1/job", json={"job_queue": "test", "job_status_webhook": webhook}
    )
    assert job_output.status_code == HTTPStatus.OK

    job_id = job_output.json["job_id"]
    job = app.get(f"/v1/job/{job_id}").json
    assert job["job_status_webhook"] == [webhook]


def test_job_post_with_unknown_webhook_type(mongo_app):
    """Test that an unknown webhook type is rejected."""
    app, _ = mongo_app
    job_output = app.post(
        "/v1/job",
        json={
            "job_queue": "test",
            "job_status_webhook": {
                "url": MATTERMOST_URL,
                "type": "carrier-pigeon",
            },
        },
    )
    assert job_output.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_job_post_with_unexpected_webhook_field(mongo_app):
    """Test that unknown fields in a webhook object are rejected."""
    app, _ = mongo_app
    job_output = app.post(
        "/v1/job",
        json={
            "job_queue": "test",
            "job_status_webhook": {"url": MATTERMOST_URL, "token": "leaked"},
        },
    )
    assert job_output.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
