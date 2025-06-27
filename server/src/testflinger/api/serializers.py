# Copyright (C) 2022 Canonical
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
"""Testflinger v1 API serializers."""

from testflinger import database


def serialize_agent_restricted_queues(agent: dict) -> dict:
    """Format restricted queue info for a single agent."""
    restricted_queues = database.get_restricted_queues()
    restricted_queues_owners = database.get_restricted_queues_owners()

    queues = agent.get("queues", [])
    restricted = [
        {
            "queue": queue,
            "restricted_to": restricted_queues_owners[queue],
        }
        for queue in queues
        if queue in restricted_queues and queue in restricted_queues_owners
    ]

    return {
        "canonical_id": agent.get("identifier"),
        "name": agent.get("name"),
        "restricted_queues": restricted,
    }
