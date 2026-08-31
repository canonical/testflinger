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
#
"""Event handling functions for Testflinger server."""

from datetime import datetime

from testflinger_common.enums import (
    AgentEventType,
    AgentState,
    ServerRoles,
    TestflingerEvent,
)

_MESSAGE_TEMPLATES = {
    AgentEventType.AGENT_ONLINE: "Agent ready to process jobs",
    AgentEventType.AGENT_OFFLINE: "Agent set to offline",
    AgentEventType.AGENT_MAINTENANCE: "Agent set to maintenance",
    AgentEventType.ONLINE_REQUESTED: "Agent set to online by {client_id}",
    AgentEventType.OFFLINE_REQUESTED: "Offline requested by {client_id}",
    AgentEventType.MAINTENANCE_REQUESTED: "Maintenance requested by {client_id}",  # noqa: E501
}


class _DefaultContext(dict):
    """Render missing placeholders instead of raising KeyError."""

    def __missing__(self, key):
        return f"<{key}>"


def format_event(event_type: TestflingerEvent, **context) -> str:
    """Interpolate the event message template with the provided context.

    :param event_type: The type of the event.
    :param context: Additional context for formatting the message.
    :return: Formatted event message based on template.
    """
    template = _MESSAGE_TEMPLATES[event_type]
    return template.format_map(_DefaultContext(context))


def build_event(
    event_type: TestflingerEvent,
    timestamp: datetime,
    detail: str = "",
    **context,
) -> dict:
    """Build an event dictionary with all relevant information.

    The event uses a formatted event message based on the event type and
    provided context.

    :param event_type: The type of the event.
    :param timestamp: The timestamp of the event.
    :param detail: Additional details for the event.
    :param context: Additional context for formatting the message.
    :return: Dictionary representing the event.
    """
    message = format_event(event_type, **context)
    return {
        "event_name": event_type,
        "timestamp": timestamp,
        "message": message,
        "detail": detail,
    }


def agent_state_change_event(
    state: str, role: ServerRoles
) -> AgentEventType | None:
    """Map a posted agent state change and a caller role to an event type."""
    # Determine if the state change was requested by a non-agent role
    # This is needed so we can later identify "who" was the requester
    requester = role != ServerRoles.AGENT

    state_to_event = {
        AgentState.OFFLINE: (
            AgentEventType.OFFLINE_REQUESTED
            if requester
            else AgentEventType.AGENT_OFFLINE
        ),
        AgentState.WAITING: (
            AgentEventType.ONLINE_REQUESTED
            if requester
            else AgentEventType.AGENT_ONLINE
        ),
        AgentState.MAINTENANCE: (
            AgentEventType.MAINTENANCE_REQUESTED
            if requester
            else AgentEventType.AGENT_MAINTENANCE
        ),
    }

    # Returns None for any invalid agent state or unmapped state
    try:
        return state_to_event.get(AgentState(state))
    except ValueError:
        return None
