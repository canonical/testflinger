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

"""Minimal client for the Jira Cloud REST API (v3).

Ref: https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/
"""

import logging
import os
from functools import cached_property
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from requests.auth import HTTPBasicAuth
from urllib3.util.retry import Retry

from testflinger.jira.exceptions import JiraConfigError, JiraRequestError

logger = logging.getLogger(__name__)

API_VERSION = 3
ADF_VERSION = 1
REQUEST_TIMEOUT = 30
ENV_SETTINGS = ("JIRA_BASE_URL", "JIRA_USER_EMAIL", "JIRA_TOKEN")


def is_configured() -> bool:
    """Return whether all Jira settings are set in the environment."""
    return all(os.environ.get(name) for name in ENV_SETTINGS)


def text_to_adf(text: str) -> dict:
    """Convert plain text to an Atlassian Document Format document.

    Each line becomes its own paragraph, as the v3 API only accepts ADF.
    """
    paragraphs = [
        {
            "type": "paragraph",
            "content": [{"type": "text", "text": line}] if line else [],
        }
        for line in text.splitlines() or [""]
    ]
    return {"type": "doc", "version": ADF_VERSION, "content": paragraphs}


class JiraClient:
    """Client for the Jira REST API."""

    def __init__(self, base_url: str, email: str, token: str):
        """Set up the client with basic (email + API token) auth.

        :raises JiraConfigError: If base_url is not an HTTPS URL with a host
        """
        parsed = urlparse(base_url)
        if parsed.scheme != "https":
            raise JiraConfigError("Jira base URL must use https://")
        if not parsed.hostname:
            raise JiraConfigError("Jira base URL must include a host")
        self.base_url = base_url.rstrip("/")
        self.auth = HTTPBasicAuth(email, token)

    @classmethod
    def from_env(cls) -> "JiraClient":
        """Create a client from JIRA_BASE_URL, JIRA_USER_EMAIL, JIRA_TOKEN."""
        values = {name: os.environ.get(name) for name in ENV_SETTINGS}
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise JiraConfigError(
                f"Missing Jira settings: {', '.join(missing)}"
            )
        return cls(
            base_url=values["JIRA_BASE_URL"],
            email=values["JIRA_USER_EMAIL"],
            token=values["JIRA_TOKEN"],
        )

    @cached_property
    def session(self) -> requests.Session:
        """Get a requests session with authentication and retries."""
        session = requests.Session()
        adapter = HTTPAdapter(max_retries=Retry(connect=5, read=2))
        session.mount("https://", adapter)
        session.auth = self.auth
        return session

    def request(
        self, method: str, endpoint: str, **kwargs
    ) -> requests.Response:
        """Make a request to the Jira REST API."""
        url = f"{self.base_url}{endpoint}"
        kwargs.setdefault("timeout", REQUEST_TIMEOUT)
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise self._error_from_response(exc.response) from exc
        except requests.RequestException as exc:
            raise JiraRequestError(None, [str(exc)]) from exc
        return response

    @staticmethod
    def _error_from_response(response: requests.Response) -> JiraRequestError:
        """Build an error from a failed Jira response."""
        try:
            body = response.json()
            if not isinstance(body, dict):
                raise ValueError
            messages = list(body.get("errorMessages", []))
            errors = body.get("errors", {})
            if isinstance(errors, dict):
                messages.extend(
                    f"{field}: {message}" for field, message in errors.items()
                )
        except ValueError:
            messages = [response.reason or "Unknown error"]
        return JiraRequestError(response.status_code, messages)

    def create_issue(
        self,
        space_key: str,
        summary: str,
        description: str,
        issue_type: str,
        labels: list[str] | None = None,
    ) -> str:
        """Create a Jira issue and return its key (e.g. TESTOPS-123)."""
        fields = {
            "project": {"key": space_key},
            "issuetype": {"name": issue_type},
            "summary": summary,
            "description": text_to_adf(description),
        }
        if labels:
            fields["labels"] = labels
        response = self.request(
            "POST",
            f"/rest/api/{API_VERSION}/issue",
            json={"fields": fields},
        )
        try:
            return response.json()["key"]
        except (ValueError, KeyError, TypeError) as exc:
            raise JiraRequestError(
                response.status_code,
                ["Unexpected response from Jira: missing issue key"],
            ) from exc
