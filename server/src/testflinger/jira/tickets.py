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
import threading

from flask import current_app
from testflinger_common.enums import AgentMode

from testflinger import database
from testflinger.jira.client import JiraClient
from testflinger.jira.exceptions import JiraError

logger = logging.getLogger(__name__)

DEFAULT_ISSUE_TYPE = "Task"


def _spawn(func, *args) -> None:
    """Run a function in a background thread.

    Jira can be slow or unreachable, and agents' heartbeats must not wait
    for it.
    """
    threading.Thread(target=func, args=args, daemon=True).start()


def _create_maintenance_ticket(app, agent_name: str) -> None:
    """Create the Jira ticket for an agent that entered maintenance."""
    try:
        with app.app_context():
            agent = database.get_agent_info_v2(agent_name) or {}
            command = agent.get("commanded_mode") or {}
            mode = agent.get("mode") or {}
            details = [
                f"Agent: {agent_name}",
                f"Location: {agent.get('location') or 'unknown'}",
            ]
            changed_by = command.get("changed_by") or mode.get("changed_by")
            if changed_by:
                details.append(f"Set by: {changed_by}")
            comment = command.get("comment") or mode.get("comment")
            if comment:
                details.append(f"Comment: {comment}")
            create_agent_ticket(
                agent_name,
                summary=f"Agent {agent_name} set to maintenance",
                description="\n".join(details),
            )
    except Exception:
        logger.exception(
            "Failed to create maintenance ticket for agent %s", agent_name
        )


def create_ticket_if_entered_maintenance(
    agent_name: str, previous_mode: str | None
) -> None:
    """Open a Jira ticket if the agent has just entered maintenance mode.

    Call this after an agent update, passing the result of
    ``database.get_agent_effective_mode`` taken before it. Tickets are only
    created on the transition into maintenance, so heartbeats, and the agent
    acknowledging a commanded maintenance, do not create duplicates.

    :param agent_name: Name of the agent that was updated.
    :param previous_mode: The agent's mode before the update.
    """
    if previous_mode == AgentMode.MAINTENANCE:
        return
    if database.get_agent_effective_mode(agent_name) != AgentMode.MAINTENANCE:
        return
    app = current_app._get_current_object()  # noqa: SLF001
    _spawn(_create_maintenance_ticket, app, agent_name)


def get_agent_space_key(agent_name: str) -> str | None:
    """Return the Jira space configured for an agent, if any.

    The space comes from the ``jira_space`` key of the agent config.
    """
    agent = database.get_agent_info(agent_name) or {}
    return agent.get("jira_space") or None


def create_agent_ticket(
    agent_name: str,
    summary: str,
    description: str,
    issue_type: str = DEFAULT_ISSUE_TYPE,
    labels: list[str] | None = None,
    client: JiraClient | None = None,
) -> str | None:
    """Create a ticket in the Jira space configured for the agent.

    :param agent_name: Agent the ticket is about
    :param summary: Ticket title
    :param description: Plain text ticket description
    :param issue_type: Name of the Jira issue type
    :param labels: Optional labels to set on the ticket
    :param client: Jira client, built from the environment if not given
    :return: The new ticket key, or None if the agent has no Jira space
        or the ticket could not be created. Jira failures are logged and
        never raised, so callers' workflows are not interrupted.
    """
    space_key = get_agent_space_key(agent_name)
    if space_key is None:
        logger.warning(
            "Agent %s has no jira_space, skipping Jira ticket: %s",
            agent_name,
            summary,
        )
        return None
    try:
        client = client or JiraClient.from_env()
        issue_key = client.create_issue(
            space_key=space_key,
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
