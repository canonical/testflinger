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

from testflinger import database
from testflinger.jira.client import JiraClient
from testflinger.jira.exceptions import JiraError

logger = logging.getLogger(__name__)

DEFAULT_ISSUE_TYPE = "Task"


def get_agent_project_key(agent_name: str) -> str | None:
    """Return the Jira project configured for an agent, if any.

    The project comes from the ``jira_project`` key of the agent config.
    """
    agent = database.get_agent_info(agent_name) or {}
    return agent.get("jira_project") or None


def create_agent_ticket(
    agent_name: str,
    summary: str,
    description: str,
    issue_type: str = DEFAULT_ISSUE_TYPE,
    labels: list[str] | None = None,
    client: JiraClient | None = None,
) -> str | None:
    """Create a ticket in the Jira project configured for the agent.

    :param agent_name: Agent the ticket is about
    :param summary: Ticket title
    :param description: Plain text ticket description
    :param issue_type: Name of the Jira issue type
    :param labels: Optional labels to set on the ticket
    :param client: Jira client, built from the environment if not given
    :return: The new ticket key, or None if the agent has no Jira project
        or the ticket could not be created. Jira failures are logged and
        never raised, so callers' workflows are not interrupted.
    """
    project_key = get_agent_project_key(agent_name)
    if project_key is None:
        logger.warning(
            "Agent %s has no jira_project, skipping Jira ticket: %s",
            agent_name,
            summary,
        )
        return None
    try:
        client = client or JiraClient.from_env()
        issue_key = client.create_issue(
            project_key=project_key,
            summary=summary,
            description=description,
            issue_type=issue_type,
            labels=labels,
        )
    except JiraError:
        logger.exception(
            "Failed to create Jira ticket for agent %s: %s",
            agent_name,
            summary,
        )
        return None
    logger.info("Created Jira ticket %s for agent %s", issue_key, agent_name)
    return issue_key
