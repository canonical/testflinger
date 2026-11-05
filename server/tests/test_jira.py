# Copyright (C) 2026 Canonical
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

"""Tests for the Jira integration."""

from unittest.mock import MagicMock

import pytest
import requests

from testflinger.jira import (
    JiraClient,
    JiraConfigError,
    JiraRequestError,
    create_agent_ticket,
    get_project_key,
)

BASE_URL = "https://jira.example.com"
ISSUE_URL = f"{BASE_URL}/rest/api/3/issue"


@pytest.fixture
def client():
    """Provide a Jira client pointing to a fake server."""
    return JiraClient(BASE_URL, "user@example.com", "token")


@pytest.mark.parametrize(
    ("location", "project"),
    [
        ("TEL-L3", "TELOPS"),
        ("tel-l10", "TELOPS"),
        ("TOR-L1", "TORLABS"),
        ("XYZ-L1", None),
        ("", None),
        (None, None),
    ],
)
def test_get_project_key(location, project):
    """Locations map to their Jira project, unknown ones to None."""
    assert get_project_key(location) == project


def test_from_env_missing(monkeypatch):
    """Missing credentials are reported by name."""
    monkeypatch.delenv("JIRA_BASE_URL", raising=False)
    monkeypatch.delenv("JIRA_USER_EMAIL", raising=False)
    monkeypatch.setenv("JIRA_TOKEN", "token")
    with pytest.raises(JiraConfigError, match="JIRA_BASE_URL.*EMAIL"):
        JiraClient.from_env()


def test_from_env(monkeypatch):
    """The client is built from the environment."""
    monkeypatch.setenv("JIRA_BASE_URL", f"{BASE_URL}/")
    monkeypatch.setenv("JIRA_USER_EMAIL", "user@example.com")
    monkeypatch.setenv("JIRA_TOKEN", "token")
    assert JiraClient.from_env().base_url == BASE_URL


def test_create_issue(client, requests_mock):
    """Issues are created with an ADF description and return their key."""
    requests_mock.post(ISSUE_URL, json={"key": "TELOPS-1"}, status_code=201)
    key = client.create_issue(
        "TELOPS", "title", "line1\nline2", "Task", labels=["a"]
    )
    assert key == "TELOPS-1"
    fields = requests_mock.last_request.body
    assert b'"key": "TELOPS"' in fields
    assert b'"labels": ["a"]' in fields
    assert fields.count(b'"type": "paragraph"') == 2


def test_create_issue_error(client, requests_mock):
    """Jira errors are surfaced with their status and message."""
    requests_mock.post(
        ISSUE_URL,
        json={"errorMessages": [], "errors": {"project": "invalid"}},
        status_code=400,
    )
    with pytest.raises(JiraRequestError, match="project: invalid") as exc:
        client.create_issue("BAD", "title", "desc", "Task")
    assert exc.value.status == 400


def test_create_issue_connection_error(client, requests_mock):
    """Connection failures are wrapped in a JiraRequestError."""
    requests_mock.post(ISSUE_URL, exc=requests.ConnectionError("down"))
    with pytest.raises(JiraRequestError):
        client.create_issue("TELOPS", "title", "desc", "Task")


def test_create_agent_ticket():
    """The ticket is created in the project of the agent location."""
    client = MagicMock()
    client.create_issue.return_value = "TORLABS-7"
    key = create_agent_ticket("TOR-L1", "title", "desc", client=client)
    assert key == "TORLABS-7"
    client.create_issue.assert_called_once_with(
        project_key="TORLABS",
        summary="title",
        description="desc",
        issue_type="Task",
        labels=None,
    )


def test_create_agent_ticket_unmapped_location():
    """No ticket is created when the location has no Jira project."""
    client = MagicMock()
    assert create_agent_ticket("XYZ-L1", "t", "d", client=client) is None
    client.create_issue.assert_not_called()
