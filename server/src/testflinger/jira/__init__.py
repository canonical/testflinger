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

"""Jira integration used to create tickets from Testflinger."""

from testflinger.jira.client import JiraClient
from testflinger.jira.exceptions import (
    JiraConfigError,
    JiraError,
    JiraRequestError,
)
from testflinger.jira.tickets import (
    create_agent_ticket,
    create_ticket_if_agent_self_maintenance,
    get_agent_space_key,
    open_maintenance_ticket,
)

__all__ = [
    "JiraClient",
    "JiraConfigError",
    "JiraError",
    "JiraRequestError",
    "create_agent_ticket",
    "create_ticket_if_agent_self_maintenance",
    "get_agent_space_key",
    "open_maintenance_ticket",
]
