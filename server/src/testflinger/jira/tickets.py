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

"""Helpers to create Jira tickets for agents."""

import logging

from testflinger.jira.client import JiraClient
from testflinger.jira.projects import get_project_key

logger = logging.getLogger(__name__)

DEFAULT_ISSUE_TYPE = "Task"


def create_agent_ticket(
    location: str | None,
    summary: str,
    description: str,
    issue_type: str = DEFAULT_ISSUE_TYPE,
    labels: list[str] | None = None,
    client: JiraClient | None = None,
) -> str | None:
    """Create a ticket in the Jira project of the agent's location.

    :param location: Agent location, used to pick the Jira project
    :param summary: Ticket title
    :param description: Plain text ticket description
    :param issue_type: Name of the Jira issue type
    :param labels: Optional labels to set on the ticket
    :param client: Jira client, built from the environment if not given
    :return: The new ticket key, or None if no project maps to the location
    :raises JiraConfigError: If the Jira credentials are not configured
    :raises JiraRequestError: If Jira rejects or fails the request
    """
    project_key = get_project_key(location)
    if project_key is None:
        logger.warning("Skipping Jira ticket creation: %s", summary)
        return None
    client = client or JiraClient.from_env()
    issue_key = client.create_issue(
        project_key=project_key,
        summary=summary,
        description=description,
        issue_type=issue_type,
        labels=labels,
    )
    logger.info("Created Jira ticket %s", issue_key)
    return issue_key
