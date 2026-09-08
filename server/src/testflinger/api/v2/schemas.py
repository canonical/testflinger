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

ValidAgentModes = [mode.value for mode in AgentMode]
ValidAgentStates = [state.value for state in AgentState]


class AgentIn(Schema):
    """Agent data input schema.

    ``mode`` is the server-commanded operating mode.  ``state`` is the
    sub-state within that mode and is only meaningful for
    :attr:`AgentMode.ONLINE` and :attr:`AgentMode.MAINTENANCE`;
    :attr:`AgentMode.OFFLINE` and :attr:`AgentMode.RESTART` carry no
    sub-state.  The combination is checked in the route handler.
    """

    identifier = fields.String(required=False)
    job_id = fields.String(required=False)
    location = fields.String(required=False)
    log = fields.List(fields.String(), required=False)
    provision_type = fields.String(required=False)
    queues = fields.List(fields.String(), required=False)
    mode = fields.String(required=False, validate=OneOf(ValidAgentModes))
    state = fields.String(required=False, validate=OneOf(ValidAgentStates))
    comment = fields.String(required=False)


class AgentOut(Schema):
    """Agent data output schema."""

    name = fields.String(required=True)
    mode = fields.String(required=False)
    mode_changed_at = fields.DateTime(required=False)
    mode_changed_by = fields.String(required=False)
    state = fields.String(required=False)
    state_changed_at = fields.DateTime(required=False)
    state_changed_by = fields.String(required=False)
    job_id = fields.String(required=False)
    queues = fields.List(fields.String(), required=False)
    location = fields.String(required=False)
    provision_type = fields.String(required=False)
    comment = fields.String(required=False)
    restricted_to = fields.Dict(required=False)
    job = fields.Nested(AgentJob, required=False, allow_none=True)
