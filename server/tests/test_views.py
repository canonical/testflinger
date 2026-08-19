# Copyright (C) 2024 Canonical
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
#
"""Unit tests for Testflinger views."""

import re
import uuid
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from unittest.mock import patch

import mongomock
import pytest
from testflinger_common.enums import LogType, TestPhase

from testflinger.views import (
    _state_duration,
    agent_detail,
    job_detail,
    queues_data,
)


def test_queues():
    """
    Test that the queues view gets the right data from both advertised and
    unadvertised queues.
    """
    mongo = mongomock.MongoClient()
    mongo.db.queues.insert_many(
        [
            {"name": "advertised_queue1", "description": "desc1"},
            {"name": "advertised_queue2", "description": "desc2"},
        ]
    )
    mongo.db.agents.insert_many(
        [
            {
                "name": "agent1",
                "queues": ["queue2", "queue4", "advertised_queue1"],
            },
            {
                "name": "agent2",
                "queues": ["queue2", "queue4", "advertised_queue2"],
            },
            # There's an unlikely chance that an agent has no queues
            {
                "name": "agent2",
            },
        ]
    )
    mongo.db.jobs.insert_many(
        [
            {
                "job_data": {"job_queue": "advertised_queue1"},
                "result_data": {"job_state": "waiting"},
            },
            {
                "job_data": {"job_queue": "advertised_queue1"},
                "result_data": {"job_state": "running"},
            },
            {
                "job_data": {"job_queue": "advertised_queue1"},
                "result_data": {"job_state": "waiting"},
            },
            {
                "job_data": {"job_queue": "advertised_queue2"},
                "result_data": {"job_state": "running"},
            },
            {
                "job_data": {"job_queue": "advertised_queue2"},
                "result_data": {"job_state": "waiting"},
            },
        ]
    )

    # Get the data from the function we use to generate the view
    with (
        patch("testflinger.views.mongo", mongo),
        patch("testflinger.database.mongo", mongo),
    ):
        data = queues_data()

    # Make sure we found all the queues, not just advertised ones
    assert len(data) == 4

    # Check that advertised queues have descriptions even though they're also
    # in agent queues without one
    advertised_queue1 = [
        queue for queue in data if queue["name"] == "advertised_queue1"
    ]
    assert len(advertised_queue1) == 1
    assert advertised_queue1[0]["description"] == "desc1"
    assert advertised_queue1[0]["numjobs"] == 3
    advertised_queue2 = [
        queue for queue in data if queue["name"] == "advertised_queue2"
    ]
    assert len(advertised_queue2) == 1
    assert advertised_queue2[0]["description"] == "desc2"
    assert advertised_queue2[0]["numjobs"] == 2


def test_agent_detail_no_provision_log(testapp):
    """
    Test that the agent detail page doesn't break when
    there's no provision log.
    """
    mongo = mongomock.MongoClient()
    mongo.db.agents.insert_one(
        {"name": "agent1", "updated_at": datetime.now(tz=timezone.utc)}
    )
    with (
        patch("testflinger.views.mongo", mongo),
        patch("testflinger.database.mongo", mongo),
    ):
        with testapp.test_request_context():
            response = agent_detail("agent1")

    pattern = r"Provision success rate for this range:</strong>\s*0%"
    assert re.search(pattern, response)


def test_agent_not_found(testapp):
    """
    Test that the agent_detail fails gracefully when
    an agent is not found.
    """
    mongo = mongomock.MongoClient()
    with patch("testflinger.views.mongo", mongo):
        with testapp.test_request_context():
            response = agent_detail("agent1")

    assert "Agent not found: agent1" in str(response.data)
    assert response.status_code == 404


def test_agent_detail_with_restricted_to(testapp):
    """Test that the agent detail page shows restricted_to field properly."""
    mongo = mongomock.MongoClient()
    mongo.db.restricted_queues.insert_one({"queue_name": "queue1"})
    mongo.db.client_permissions.insert_one(
        {
            "client_id": "test-client-id",
            "allowed_queues": ["queue1"],
        }
    )
    mongo.db.agents.insert_one(
        {
            "name": "agent1",
            "queues": ["queue1", "queue2"],
            "updated_at": datetime.now(tz=timezone.utc),
        }
    )
    with (
        patch("testflinger.views.mongo", mongo),
        patch("testflinger.database.mongo", mongo),
    ):
        with testapp.test_request_context():
            response = agent_detail("agent1")

    html = str(response)
    assert "(restricted to: test-client-id)" in html


def test_agent_detail_with_non_advertised_queue(testapp):
    """Test agent detail with advertised and non-advertised queues."""
    mongo = mongomock.MongoClient()
    # Insert one advertised queue
    mongo.db.queues.insert_one(
        {"name": "advertised_queue", "description": "advertised description"}
    )
    # Agent listens to both advertised and non-advertised queues
    mongo.db.agents.insert_one(
        {
            "name": "agent1",
            "queues": ["advertised_queue", "non_advertised_queue"],
            "updated_at": datetime.now(tz=timezone.utc),
        }
    )
    mongo.db.jobs.insert_many(
        [
            {
                "job_data": {"job_queue": "advertised_queue"},
                "result_data": {"job_state": "waiting"},
            },
            {
                "job_data": {"job_queue": "non_advertised_queue"},
                "result_data": {"job_state": "running"},
            },
        ]
    )

    with (
        patch("testflinger.views.mongo", mongo),
        patch("testflinger.database.mongo", mongo),
    ):
        with testapp.test_request_context():
            response = agent_detail("agent1")

    html = str(response)
    # Should include both advertised and non-advertised queues
    assert "advertised_queue" in html
    assert "non_advertised_queue" in html
    # Non-advertised queue creates dummy data with empty description
    assert "advertised description" in html


def test_job_not_found(testapp):
    """
    Test that the job_detail fails gracefully when
    a job is not found.
    """
    mongo = mongomock.MongoClient()
    with patch("testflinger.views.mongo", mongo):
        with testapp.test_request_context():
            response = job_detail("job1")

    assert "Job not found: job1" in str(response.data)
    assert response.status_code == 404


def test_job_results_mongo_logs(testapp):
    """Test that the job_detail view formats logs from MongoDB correctly."""
    mongo = mongomock.MongoClient()
    job_id = str(uuid.uuid4())
    mongo.db.jobs.insert_one(
        {
            "job_id": job_id,
            "created_at": datetime.now(timezone.utc),
            "job_data": {"job_queue": "queue1", "provision_data": "skip"},
            "result_data": {
                "status": {TestPhase.PROVISION: 0, TestPhase.TEST: 1},
                "device_info": {
                    "agent_name": "agent1",
                    "device_ip": "1.1.1.1",
                },
                "job_state": "complete",
            },
        }
    )
    # Insert log fragments into the logs collection
    mongo.db.logs.insert_many(
        [
            {
                "job_id": job_id,
                "log_type": LogType.STANDARD_OUTPUT,
                "phase": TestPhase.PROVISION,
                "fragment_number": 0,
                "timestamp": datetime.now(tz=timezone.utc),
                "log_data": "Provision log content",
            },
            {
                "job_id": job_id,
                "log_type": LogType.STANDARD_OUTPUT,
                "phase": TestPhase.TEST,
                "fragment_number": 0,
                "timestamp": datetime.now(tz=timezone.utc),
                "log_data": "Test log content",
            },
        ]
    )
    with (
        patch("testflinger.views.mongo", mongo),
    ):
        with testapp.test_request_context():
            response = job_detail(job_id)

    html = str(response)
    # Check that formatted logs are present
    assert "Provision log content" in html
    assert "Test log content" in html
    # Check that phase statuses are present
    assert "Exit Status:</span> 0" in html
    assert "Exit Status:</span> 1" in html


@pytest.mark.parametrize("endpoint", ["/agents", "/jobs", "/queues"])
def test_unauthorized_view_access(oidc_app, endpoint):
    """Test 401 error when OIDC is enabled but user is not authenticated."""
    app, _ = oidc_app
    with app.test_client() as client:
        response = client.get(endpoint)
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert "You need to sign in to access this page." in str(response.data)


@pytest.mark.parametrize("endpoint", ["/agents", "/jobs", "/queues"])
def test_authorized_view_access(oidc_app, endpoint):
    """Test views are available when OIDC is enabled and user authenticated."""
    app, _ = oidc_app
    mongo = mongomock.MongoClient()
    with app.test_client() as client, patch("testflinger.views.mongo", mongo):
        with client.session_transaction() as sess:
            sess["user"] = "testuser"
        response = client.get(endpoint)
    assert response.status_code == HTTPStatus.OK


def test_home_accessible_without_auth_when_oidc_enabled(oidc_app):
    """Test home page is accessible even when OIDC is enabled and no user."""
    app, _ = oidc_app
    with app.test_client() as client:
        response = client.get("/")
    assert response.status_code == HTTPStatus.OK


# ---------------------------------------------------------------------------
# Tests for _state_duration
# ---------------------------------------------------------------------------


def test_state_duration_none_returns_dash():
    """_state_duration(None) returns '—'."""
    assert _state_duration(None) == "—"


def test_state_duration_future_returns_dash():
    """_state_duration with a future timestamp returns '—'."""
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    assert _state_duration(future) == "—"


def test_state_duration_zero_seconds():
    """_state_duration for a just-now timestamp returns '0m'."""
    now = datetime.now(timezone.utc)
    assert _state_duration(now) == "0m"


def test_state_duration_minutes_only():
    """_state_duration for 45 minutes ago returns '45m'."""
    ts = datetime.now(timezone.utc) - timedelta(minutes=45)
    assert _state_duration(ts) == "45m"


def test_state_duration_hours_and_minutes():
    """_state_duration for 2h30m ago returns '2h 30m'."""
    ts = datetime.now(timezone.utc) - timedelta(hours=2, minutes=30)
    assert _state_duration(ts) == "2h 30m"


def test_state_duration_days_hours_minutes():
    """_state_duration for 1d 3h 15m ago returns '1d 3h 15m'."""
    ts = datetime.now(timezone.utc) - timedelta(days=1, hours=3, minutes=15)
    assert _state_duration(ts) == "1d 3h 15m"


def test_state_duration_exact_one_hour():
    """_state_duration for exactly 1 hour returns '1h' (0 minutes omitted)."""
    ts = datetime.now(timezone.utc) - timedelta(hours=1)
    assert _state_duration(ts) == "1h"


def test_state_duration_naive_datetime():
    """_state_duration handles a naive (tz-unaware) datetime."""
    naive = datetime.utcnow() - timedelta(minutes=5)  # noqa: DTZ003
    result = _state_duration(naive)
    assert result == "5m"


# ---------------------------------------------------------------------------
# Tests for agent_state_update (POST /agents/<id>/state)
# ---------------------------------------------------------------------------


def test_agent_state_update_forbidden_without_oidc(testapp):
    """agent_state_update always returns 403 when OIDC is not configured."""
    mongo_client = mongomock.MongoClient()
    mongo_client.db.agents.insert_one({"name": "agent1", "mode": "online"})
    with (
        patch("testflinger.views.mongo", mongo_client),
        patch("testflinger.database.mongo", mongo_client),
    ):
        with testapp.test_client() as client:
            response = client.post(
                "/agents/agent1/state",
                data={"mode": "offline", "comment": "test"},
            )
    assert response.status_code == HTTPStatus.FORBIDDEN


def test_agent_state_update_unauthorized_without_session(oidc_app):
    """agent_state_update returns 401 when no user_email is in session."""
    app, _ = oidc_app
    mongo_client = mongomock.MongoClient()
    with (
        app.test_client() as client,
        patch("testflinger.views.mongo", mongo_client),
        patch("testflinger.database.mongo", mongo_client),
    ):
        # No session set — user_email will be absent
        response = client.post(
            "/agents/agent1/state",
            data={"mode": "offline", "comment": "test"},
        )
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_agent_state_update_forbidden_non_admin(oidc_app):
    """agent_state_update returns 403 when the logged-in user is not admin."""
    app, _ = oidc_app
    non_admin_email = "user@example.com"
    mongo_client = mongomock.MongoClient()
    mongo_client.db.client_permissions.insert_one(
        {"client_id": non_admin_email, "role": "contributor"}
    )
    with (
        app.test_client() as client,
        patch("testflinger.views.mongo", mongo_client),
        patch("testflinger.database.mongo", mongo_client),
    ):
        with client.session_transaction() as sess:
            sess["user"] = "testuser"
            sess["user_email"] = non_admin_email
        response = client.post(
            "/agents/agent1/state",
            data={"mode": "offline", "comment": "test"},
        )
    assert response.status_code == HTTPStatus.FORBIDDEN


def test_agent_state_update_invalid_mode(oidc_app):
    """agent_state_update returns 400 for an unrecognised mode value."""
    app, _ = oidc_app
    admin_email = "admin@example.com"
    mongo_client = mongomock.MongoClient()
    mongo_client.db.client_permissions.insert_one(
        {"client_id": admin_email, "role": "admin"}
    )
    with (
        app.test_client() as client,
        patch("testflinger.views.mongo", mongo_client),
        patch("testflinger.database.mongo", mongo_client),
    ):
        with client.session_transaction() as sess:
            sess["user"] = "admin"
            sess["user_email"] = admin_email
        response = client.post(
            "/agents/agent1/state",
            data={"mode": "bogus", "comment": "test"},
        )
    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_agent_state_update_offline_requires_comment(oidc_app):
    """agent_state_update returns 400 when mode=offline has no comment."""
    app, _ = oidc_app
    admin_email = "admin@example.com"
    mongo_client = mongomock.MongoClient()
    mongo_client.db.client_permissions.insert_one(
        {"client_id": admin_email, "role": "admin"}
    )
    with (
        app.test_client() as client,
        patch("testflinger.views.mongo", mongo_client),
        patch("testflinger.database.mongo", mongo_client),
    ):
        with client.session_transaction() as sess:
            sess["user"] = "admin"
            sess["user_email"] = admin_email
        response = client.post(
            "/agents/agent1/state",
            data={"mode": "offline"},
        )
    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_agent_state_update_success_sets_mode(oidc_app):
    """agent_state_update persists the new mode and redirects."""
    app, _ = oidc_app
    admin_email = "admin@example.com"
    mongo_client = mongomock.MongoClient()
    mongo_client.db.client_permissions.insert_one(
        {"client_id": admin_email, "role": "admin"}
    )
    mongo_client.db.agents.insert_one(
        {
            "name": "agent1",
            "mode": "online",
            "updated_at": datetime.now(timezone.utc),
        }
    )
    with (
        app.test_client() as client,
        patch("testflinger.views.mongo", mongo_client),
        patch("testflinger.database.mongo", mongo_client),
    ):
        with client.session_transaction() as sess:
            sess["user"] = "admin"
            sess["user_email"] = admin_email
        response = client.post(
            "/agents/agent1/state",
            data={"mode": "offline", "comment": "scheduled downtime"},
        )
    # Expect a redirect back to the agent detail page
    assert response.status_code in (
        HTTPStatus.FOUND,
        HTTPStatus.SEE_OTHER,
        HTTPStatus.MOVED_PERMANENTLY,
    )
    record = mongo_client.db.agents.find_one({"name": "agent1"})
    assert record["mode"] == "offline"
    assert record["comment"] == "scheduled downtime"
    assert record["mode_changed_by"] == admin_email


def _make_oidc_admin_client(oidc_app, mongo_client, admin_email):
    """Return a test client with an admin session."""
    app, _ = oidc_app
    mongo_client.db.client_permissions.insert_one(
        {"client_id": admin_email, "role": "admin"}
    )
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "admin"
        sess["user_email"] = admin_email
    return app, client


@pytest.mark.parametrize(
    "new_mode,comment,expected_mode",
    [
        ("maintenance", "Replacing hardware", "maintenance"),
        ("restart", "", "restart"),
        ("online", "", "online"),
    ],
)
def test_agent_state_update_all_modes(
    oidc_app, new_mode, comment, expected_mode
):
    """agent_state_update persists every valid mode correctly.

    - maintenance requires a comment
    - restart and online do not
    """
    admin_email = "admin@example.com"
    mongo_client = mongomock.MongoClient()
    app, client = _make_oidc_admin_client(oidc_app, mongo_client, admin_email)

    mongo_client.db.agents.insert_one(
        {
            "name": "agent1",
            "mode": "online",
            "updated_at": datetime.now(timezone.utc),
        }
    )

    form_data = {"mode": new_mode}
    if comment:
        form_data["comment"] = comment

    with (
        patch("testflinger.views.mongo", mongo_client),
        patch("testflinger.database.mongo", mongo_client),
    ):
        response = client.post("/agents/agent1/state", data=form_data)

    assert response.status_code in (
        HTTPStatus.FOUND,
        HTTPStatus.SEE_OTHER,
        HTTPStatus.MOVED_PERMANENTLY,
    ), f"Expected redirect for mode={new_mode!r}, got {response.status_code}"

    record = mongo_client.db.agents.find_one({"name": "agent1"})
    assert record["mode"] == expected_mode


def test_agent_state_update_maintenance_requires_comment(oidc_app):
    """agent_state_update returns 400 when mode=maintenance has no comment."""
    admin_email = "admin@example.com"
    mongo_client = mongomock.MongoClient()
    app, client = _make_oidc_admin_client(oidc_app, mongo_client, admin_email)

    with (
        patch("testflinger.views.mongo", mongo_client),
        patch("testflinger.database.mongo", mongo_client),
    ):
        response = client.post(
            "/agents/agent1/state", data={"mode": "maintenance"}
        )

    assert response.status_code == HTTPStatus.BAD_REQUEST
