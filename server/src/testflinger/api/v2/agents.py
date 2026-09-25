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
"""Agent endpoints for the v2 API.

Adds `mode` to agent data.
"""

from datetime import datetime, timezone
from http import HTTPStatus

from apiflask import abort
from flask import g, jsonify
from testflinger_common.enums import AgentMode, ServerRoles

from testflinger import database
from testflinger.api.auth import authenticate, require_role
from testflinger.api.v2 import schemas, v2


def _attach_restricted_to(agents: list[dict]) -> None:
    """Annotate each agent with the owners of its restricted queues.

    :param agents: Agent records to annotate in place.
    """
    restricted_queues = database.get_restricted_queues()
    restricted_queues_owners = database.get_restricted_queues_owners()

    for agent in agents:
        agent["restricted_to"] = {
            queue: restricted_queues_owners[queue]
            for queue in agent.get("queues", [])
            if queue in restricted_queues
            and restricted_queues_owners.get(queue)
        }


def _check_mode_state(json_data: dict) -> list[str]:
    """Validate the mode/state combination of an incoming agent update.

    A mode and a sub-state are set by different actors: an admin
    commands the mode, the agent reports the state.  Either may arrive
    on its own.  The one combination that cannot be honoured is a
    sub-state on a mode that has none.

    :param json_data: Parsed request body; not modified.
    :return: Field names to unset on the stored record.
    :raises HTTPException: 400 if mode and state contradict each other.
    """
    mode = json_data.get("mode")
    if mode is None or AgentMode(mode).has_substate:
        return []

    if json_data.get("state") is not None:
        abort(
            HTTPStatus.BAD_REQUEST,
            message=f"mode={mode} does not take a state",
        )
    # Drop any sub-state left over from the previous mode.
    return ["state"]


@v2.get("/agents/data")
@authenticate
@require_role(ServerRoles.ADMIN, ServerRoles.MANAGER, ServerRoles.CONTRIBUTOR)
@v2.output(schemas.AgentOut(many=True))
def agents_get_all():
    """Get all agent data."""
    agents = database.get_agents()
    _attach_restricted_to(agents)
    return jsonify(agents)


@v2.get("/agents/<agent_name>/data")
@authenticate
@require_role(*ServerRoles)
@v2.output(schemas.AgentOut)
def agents_get_one(agent_name):
    """Get the information from a specified agent.

    :param agent_name:
        String with the name of the agent to retrieve information from.
    :return:
        JSON data with the specified agent information.
    """
    agent_data = database.get_agent_info(agent_name)
    if not agent_data:
        return {}, HTTPStatus.NOT_FOUND

    _attach_restricted_to([agent_data])
    return jsonify(agent_data)


@v2.post("/agents/<agent_name>/data")
@authenticate
@require_role(ServerRoles.ADMIN, ServerRoles.MANAGER, ServerRoles.AGENT)
@v2.input(schemas.AgentIn, location="json")
def agents_post(agent_name, json_data):
    """Post information about the agent to the server.

    The json sent to this endpoint may contain data such as the following:
    {
        "mode": string,  # Commanded operating mode of the agent
        "state": string, # Sub-state within that mode, where applicable
        "queues": array[string], # Queues the device is listening on
        "location": string, # Location of the device
        "job_id": string, # Job ID the device is running, if any
        "log": array[string], # push and keep only the last 100 lines
    }
    """
    unset = _check_mode_state(json_data)

    # Only an agent registering itself may bring a new record into being.
    is_agent = g.role == ServerRoles.AGENT
    if not is_agent and not database.get_agent_info(agent_name):
        abort(HTTPStatus.NOT_FOUND, message="Agent not found")

    json_data["name"] = agent_name
    json_data["updated_at"] = datetime.now(timezone.utc)
    # extract log from data so we can push it instead of setting it
    log = json_data.pop("log", [])

    database.upsert_agent_document(
        agent_name,
        json_data,
        log,
        changed_by=g.client_id,
        upsert=is_agent,
        unset=unset,
    )

    # Set a session cookie to identify the agent for future requests
    response = jsonify({"status": "OK"})
    response.set_cookie(
        "agent_name", agent_name, httponly=True, samesite="Strict"
    )
    return response
