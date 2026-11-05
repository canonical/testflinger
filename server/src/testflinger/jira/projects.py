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

"""Mapping of lab locations to the Jira project that tracks them."""

import logging

logger = logging.getLogger(__name__)

# Keyed by the upper-case prefix of an agent location, e.g. "TEL-L3" -> "TEL"
LOCATION_PROJECTS = {
    "TEL": "TELOPS",
    "TOR": "TORLABS",
}


def get_project_key(location: str | None) -> str | None:
    """Return the Jira project key for a location, or None if unmapped."""
    prefix = (location or "").split("-")[0].strip().upper()
    project_key = LOCATION_PROJECTS.get(prefix)
    if project_key is None:
        logger.warning(
            "No Jira project mapped for location %r", location or ""
        )
    return project_key
