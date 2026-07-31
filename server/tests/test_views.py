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
from datetime import datetime, timezone
from http import HTTPStatus
from unittest.mock import patch

import mongomock
import pytest
import yaml
from testflinger_common.enums import LogType, TestPhase

from testflinger.views import (
    agent_detail,
    as_yaml,
    build_job_yaml,
    highlight,
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


def test_build_job_yaml():
    """build_job_yaml produces a submittable, ordered job definition."""
    job_data = {
        "job_queue": "queue1",
        "provision_data": {"distro": "jammy"},
        "test_data": {"test_cmds": "echo hello\nlsb_release -a\n"},
        # Runtime-only keys must not leak into the definition
        "job_id": "should-not-appear",
    }

    job_yaml = build_job_yaml(job_data)

    parsed = yaml.safe_load(job_yaml)
    assert parsed == {
        "job_queue": "queue1",
        "provision_data": {"distro": "jammy"},
        "test_data": {"test_cmds": "echo hello\nlsb_release -a\n"},
    }
    # job_queue is rendered first, multiline test_cmds use a literal block
    assert job_yaml.startswith("job_queue: queue1")
    assert "test_cmds: |" in job_yaml
    assert "should-not-appear" not in job_yaml


def test_job_definition_fields_derived_from_schema():
    """Definition fields track the Job schema minus server-managed fields.

    Deriving the list keeps new submittable fields from being silently
    dropped while still excluding fields the server assigns.
    """
    from testflinger.api.schemas import Job
    from testflinger.views import JOB_DEFINITION_FIELDS

    schema_fields = set(Job().fields)
    server_managed = {"job_id", "parent_job_id"}

    # Every submittable schema field is included; server-managed ones are not.
    assert set(JOB_DEFINITION_FIELDS) == schema_fields - server_managed
    assert server_managed.isdisjoint(JOB_DEFINITION_FIELDS)


def test_job_detail_has_copy_button(testapp):
    """The job detail view exposes a copy-job-YAML button and payload."""
    mongo = mongomock.MongoClient()
    job_id = str(uuid.uuid4())
    mongo.db.jobs.insert_one(
        {
            "job_id": job_id,
            "created_at": datetime.now(timezone.utc),
            "job_data": {
                "job_queue": "queue1",
                "provision_data": {"distro": "jammy"},
            },
            "result_data": {"job_state": "complete"},
        }
    )
    with patch("testflinger.views.mongo", mongo):
        with testapp.test_request_context():
            response = job_detail(job_id)

    html = str(response)
    assert 'data-copy-target="#job-yaml-content"' in html
    assert 'id="job-yaml-content"' in html
    assert "job_queue: queue1" in html


def test_as_yaml_filter():
    """as_yaml renders mappings as YAML and passes strings through."""
    assert as_yaml({"distro": "jammy"}) == "distro: jammy"
    # Legacy string values (e.g. provision_data: skip) are shown verbatim
    assert as_yaml("skip") == "skip"
    assert as_yaml(None) is None


def test_highlight_filter():
    """Highlight wraps code in Pygments token markup, escaping content."""
    yaml_html = highlight("distro: jammy", "yaml")
    assert "jammy" in yaml_html
    assert 'class="' in yaml_html  # Pygments token spans

    # The script content is HTML-escaped (no raw tags leak through)
    bash_html = highlight("echo '<script>'", "bash")
    assert "<script>" not in bash_html
    assert "&lt;script&gt;" in bash_html

    # Unknown languages and empty input fall back gracefully
    assert highlight("plain text", "unknown") == "plain text"
    assert highlight("", "yaml") == ""


def test_job_detail_renders_yaml_not_python_repr(testapp):
    """Job detail shows a default Job YAML tab and YAML-rendered sections."""
    mongo = mongomock.MongoClient()
    job_id = str(uuid.uuid4())
    mongo.db.jobs.insert_one(
        {
            "job_id": job_id,
            "created_at": datetime.now(timezone.utc),
            "job_data": {
                "job_queue": "queue1",
                "provision_data": {"distro": "jammy"},
                "test_data": {"test_cmds": "echo hello"},
            },
            "result_data": {"job_state": "complete"},
        }
    )
    with patch("testflinger.views.mongo", mongo):
        with testapp.test_request_context():
            response = job_detail(job_id)

    html = str(response)
    # The Job YAML tab exists and is selected by default
    assert 'id="job-yaml-tab"' in html
    assert 'aria-controls="job-yaml"' in html
    # Sections render as YAML, not as a Python dict repr
    assert "{'distro'" not in html
    # Highlighting is applied server-side via Pygments
    assert 'class="language-yaml pygments"' in html
    assert 'class="language-bash pygments"' in html


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
