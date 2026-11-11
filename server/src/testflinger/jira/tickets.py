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
from dataclasses import dataclass, field
from datetime import datetime, timezone

from flask import current_app
from testflinger_common.enums import AgentMode

from testflinger import database
from testflinger.jira.client import JiraClient
from testflinger.jira.exceptions import JiraError

logger = logging.getLogger(__name__)

DEFAULT_ISSUE_TYPE = "Task"
SERVER_CLIENT_ID = "testflinger-server"


@dataclass(frozen=True)
class MaintenanceReport:
    """What an agent reported when it put itself into maintenance."""

    client_id: str | None
    time: str
    comment: str | None = None
    links: list[dict] = field(default_factory=list)


def _spawn(func, *args) -> None:
    """Run a function in a background thread.

    Jira can be slow or unreachable, and agents' heartbeats must not wait
    for it.
    """
    threading.Thread(target=func, args=args, daemon=True).start()


def _ticket_description(
    agent_name: str, agent: dict, report: MaintenanceReport
) -> str:
    """Build the ticket text from the agent record and its report."""
    lines = [
        f"Agent: {agent_name}",
        f"Reported by: {report.client_id or 'unknown'}",
        f"Time: {report.time}",
        f"Location: {agent.get('location') or 'unknown'}",
        f"Queues: {', '.join(agent.get('queues') or []) or 'none'}",
        f"Provision type: {agent.get('provision_type') or 'unknown'}",
        f"Identifier: {agent.get('identifier') or 'unknown'}",
    ]
    if report.comment:
        lines.append(f"Comment: {report.comment}")
    links = report.links or agent.get("links") or []
    lines.extend(f"Link ({link['label']}): {link['url']}" for link in links)
    return "\n".join(lines)


def _create_maintenance_ticket(
    app, agent_name: str, report: MaintenanceReport
) -> None:
    """Create the ticket for an agent that put itself in maintenance.

    Afterwards the server commands maintenance too, so both sides agree and
    the comment points at the ticket.
    """
    try:
        with app.app_context():
            agent = database.get_agent_info_v2(agent_name) or {}
            issue_key = create_agent_ticket(
                agent_name,
                summary=f"Agent {agent_name} went into maintenance on its own",
                description=_ticket_description(agent_name, agent, report),
            )
            if issue_key:
                comment = f"Jira ticket {issue_key}"
            else:
                comment = "Jira ticket could not be created, see server logs"
            mode, commanded_mode = database.get_agent_mode_snapshot(agent_name)
            # Don't override someone who acted while the ticket was created
            if mode == AgentMode.MAINTENANCE and not commanded_mode:
                database.set_agent_commanded_mode(
                    agent_name,
                    AgentMode.MAINTENANCE.value,
                    comment,
                    changed_by=SERVER_CLIENT_ID,
                )
    except Exception:
        logger.exception(
            "Failed to create maintenance ticket for agent %s", agent_name
        )


def create_ticket_if_agent_self_maintenance(
    agent_name: str,
    before: tuple[str | None, str | None],
    *,
    client_id: str | None,
    comment: str | None = None,
    links: list[dict] | None = None,
) -> None:
    """Open a Jira ticket if an agent put itself into maintenance mode.

    Call this after an agent's report was stored, passing the result of
    ``database.get_agent_mode_snapshot`` taken before it. A ticket is only
    created when the reported mode changes to maintenance and no mode was
    commanded, since a commanded mode means someone is already handling the
    agent. Heartbeats that keep the agent in maintenance don't match.

    :param agent_name: Name of the agent that reported.
    :param before: ``(reported_mode, commanded_mode)`` before the report.
    :param client_id: Client id the report was made with.
    :param comment: Comment included in the report, if any.
    :param links: Links included in the report, if any.
    """
    previous_mode, commanded_mode = before
    if commanded_mode or previous_mode == AgentMode.MAINTENANCE:
        return
    current_mode, _ = database.get_agent_mode_snapshot(agent_name)
    if current_mode != AgentMode.MAINTENANCE:
        return
    # Agents without a space keep their existing behaviour
    if get_agent_space_key(agent_name) is None:
        return
    report = MaintenanceReport(
        client_id=client_id,
        time=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        comment=comment,
        links=links or [],
    )
    app = current_app._get_current_object()  # noqa: SLF001
    _spawn(_create_maintenance_ticket, app, agent_name, report)


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
