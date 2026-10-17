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
"""Testflinger v2 OpenAPI schemas."""

from apiflask import Schema, fields
from apiflask.validators import OneOf
from testflinger_common.enums import AgentMode, AgentState

from testflinger.api.schemas import AgentJob

# Valid agent modes (v2 API constraint; v1 has no validation)
ValidAgentModes = [mode.value for mode in AgentMode]

# Valid agent input states (excludes UNKNOWN which v1 can send)
# UNKNOWN is excluded because v2 agents should report determinate states.
# V1 agents can send "unknown" (the v1 API has no validation), but the
# server translates it to ONLINE mode with no sub-state when stored.
ValidAgentInputStates = [
    state.value for state in AgentState if state != AgentState.UNKNOWN
]


class AgentInV2(Schema):
    """Agent data input schema (agent-role callers only).

    ``mode`` is the agent's current operating mode (reported by the agent).
    ``state`` is the sub-state within the active mode and is only meaningful
    for :attr:`AgentMode.ONLINE` and :attr:`AgentMode.MAINTENANCE`;
    :attr:`AgentMode.OFFLINE` and :attr:`AgentMode.RESTART` carry no
    sub-state.  The mode/state combination is checked in the route handler.

    Note:
    ``commanded_mode`` and ``comment`` are intentionally absent: those are
    set by admin callers via
    ``PATCH /v2/agents/{name}/commanded_mode``.
    """

    identifier = fields.String(required=False)
    job_id = fields.String(required=False)
    location = fields.String(required=False)
    log = fields.List(fields.String(), required=False)
    provision_type = fields.String(required=False)
    queues = fields.List(fields.String(), required=False)
    mode = fields.String(required=False, validate=OneOf(ValidAgentModes))
    comment = fields.String(required=False)
    state = fields.String(
        required=False, validate=OneOf(ValidAgentInputStates)
    )


class CommandedModeIn(Schema):
    """Input schema for the PATCH commanded_mode endpoint.

    ``commanded_mode`` is required; ``comment`` is optional and an empty
    string clears any existing comment on the agent record.
    """

    commanded_mode = fields.String(
        required=True, validate=OneOf(ValidAgentModes)
    )
    comment = fields.String(required=False, load_default="")


class ModeOut(Schema):
    """Nested schema for mode information with metadata."""

    value = fields.String(required=False, validate=OneOf(ValidAgentModes))
    changed_at = fields.DateTime(required=False)
    changed_by = fields.String(required=False)
    comment = fields.String(required=False)


class CommandedModeOut(Schema):
    """Nested schema for commanded mode information with metadata."""

    value = fields.String(required=False, validate=OneOf(ValidAgentModes))
    changed_at = fields.DateTime(required=False)
    changed_by = fields.String(required=False)
    comment = fields.String(required=False)


class StateOut(Schema):
    """Nested schema for state information with metadata."""

    value = fields.String(required=False)
    changed_at = fields.DateTime(required=False)


class AgentOutV2(Schema):
    """Agent data output schema.

    The schema uses nested structures to group related fields:
    - ``mode``: Operating mode with metadata (value, changed_at, changed_by)
    - ``commanded_mode``: Commanded mode with metadata (value, changed_at,
      changed_by, comment)
    - ``state``: Sub-state within active mode with metadata (value, changed_at)
    """

    name = fields.String(required=True)
    mode = fields.Nested(ModeOut, required=False)
    commanded_mode = fields.Nested(CommandedModeOut, required=False)
    state = fields.Nested(StateOut, required=False)
    job_id = fields.String(required=False)
    queues = fields.List(fields.String(), required=False)
    location = fields.String(required=False)
    provision_type = fields.String(required=False)
    restricted_to = fields.Dict(required=False)
    job = fields.Nested(AgentJob, required=False, allow_none=True)
