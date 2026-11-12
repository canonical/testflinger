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

from unittest.mock import MagicMock, patch

import pytest
import requests

from testflinger import database
from testflinger.jira import (
    JiraClient,
    JiraConfigError,
    JiraRequestError,
    create_agent_ticket,
    get_agent_space_key,
)

BASE_URL = "https://jira.example.com"
ISSUE_URL = f"{BASE_URL}/rest/api/3/issue"


@pytest.fixture
def client():
    """Provide a Jira client pointing to a fake server."""
    return JiraClient(BASE_URL, "user@example.com", "token")


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


@pytest.mark.parametrize("url", ["http://jira.example.com", "jira.example"])
def test_non_https_url_rejected(url):
    """The API token is never sent over a non-HTTPS connection."""
    with pytest.raises(JiraConfigError, match="https"):
        JiraClient(url, "user@example.com", "token")


def test_url_without_host_rejected():
    """A base URL must include a host."""
    with pytest.raises(JiraConfigError, match="host"):
        JiraClient("https:///", "user@example.com", "token")


def test_create_issue(client, requests_mock):
    """Issues are created with an ADF description and return their key."""
    requests_mock.post(ISSUE_URL, json={"key": "TESTOPS-1"}, status_code=201)
    key = client.create_issue(
        "TESTOPS", "title", "line1\nline2", "Task", labels=["a"]
    )
    assert key == "TESTOPS-1"
    fields = requests_mock.last_request.body
    assert b'"key": "TESTOPS"' in fields
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


@pytest.mark.parametrize("body", [[], "oops", {"errors": ["bad"]}])
def test_create_issue_unexpected_error_body(client, requests_mock, body):
    """Error bodies that aren't Jira's usual object still give a JiraError."""
    requests_mock.post(ISSUE_URL, json=body, status_code=502)
    with pytest.raises(JiraRequestError) as exc:
        client.create_issue("TESTOPS", "title", "desc", "Task")
    assert exc.value.status == 502


@pytest.mark.parametrize(
    "kwargs", [{"text": "not json"}, {"json": {}}, {"json": ["TESTOPS-1"]}]
)
def test_create_issue_malformed_success(client, requests_mock, kwargs):
    """A success response without an issue key gives a JiraRequestError."""
    requests_mock.post(ISSUE_URL, status_code=201, **kwargs)
    with pytest.raises(JiraRequestError, match="Unexpected") as exc:
        client.create_issue("TESTOPS", "title", "desc", "Task")
    assert exc.value.status == 201


def test_create_issue_connection_error(client, requests_mock):
    """Connection failures are wrapped in a JiraRequestError."""
    requests_mock.post(ISSUE_URL, exc=requests.ConnectionError("down"))
    with pytest.raises(JiraRequestError):
        client.create_issue("TESTOPS", "title", "desc", "Task")


def test_get_agent_space_key():
    """The space is read from the agent's stored config."""
    with patch.object(
        database, "get_agent_info", return_value={"jira_space": "TESTOPS"}
    ):
        assert get_agent_space_key("agent1") == "TESTOPS"


@pytest.mark.parametrize("agent", [None, {}, {"jira_space": ""}])
def test_get_agent_space_key_missing(agent):
    """Agents without a configured space (or unknown ones) give None."""
    with patch.object(database, "get_agent_info", return_value=agent):
        assert get_agent_space_key("agent1") is None


def test_create_agent_ticket():
    """The ticket is created in the space configured for the agent."""
    client = MagicMock()
    client.create_issue.return_value = "TORLABS-7"
    with patch.object(
        database, "get_agent_info", return_value={"jira_space": "TORLABS"}
    ):
        key = create_agent_ticket("agent1", "title", "desc", client=client)
    assert key == "TORLABS-7"
    client.create_issue.assert_called_once_with(
        space_key="TORLABS",
        summary="title",
        description="desc",
        issue_type="Task",
        labels=None,
    )


@pytest.mark.parametrize(
    "error", [JiraRequestError(500, ["boom"]), JiraConfigError("missing")]
)
def test_create_agent_ticket_failure(error, caplog):
    """Jira failures are logged and swallowed instead of raised."""
    client = MagicMock()
    client.create_issue.side_effect = error
    with patch.object(
        database, "get_agent_info", return_value={"jira_space": "TESTOPS"}
    ):
        assert create_agent_ticket("agent1", "t", "d", client=client) is None
    assert "Failed to create Jira ticket for agent agent1" in caplog.text


def test_create_agent_ticket_malformed_success(client, requests_mock):
    """A success response without an issue key is swallowed."""
    requests_mock.post(ISSUE_URL, text="not json", status_code=201)
    with patch.object(
        database, "get_agent_info", return_value={"jira_space": "TESTOPS"}
    ):
        assert create_agent_ticket("agent1", "t", "d", client=client) is None


def test_create_agent_ticket_missing_credentials(monkeypatch):
    """Missing credentials don't raise when no client is given."""
    monkeypatch.delenv("JIRA_BASE_URL", raising=False)
    with patch.object(
        database, "get_agent_info", return_value={"jira_space": "TESTOPS"}
    ):
        assert create_agent_ticket("agent1", "t", "d") is None


def test_create_agent_ticket_no_space():
    """No ticket is created when the agent has no Jira space."""
    client = MagicMock()
    with patch.object(database, "get_agent_info", return_value={}):
        assert create_agent_ticket("agent1", "t", "d", client=client) is None
    client.create_issue.assert_not_called()
