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
"""Helpers module for v1 api."""

import re
from http import HTTPStatus

from apiflask import abort

PATH_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+(?:\/[a-zA-Z0-9_-]+)*$")


def validate_secret_path(path):
    """Validate the secret path format."""
    if not PATH_PATTERN.match(path):
        abort(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            message=(
                f"Invalid value '{path}', not a valid path. \n"
                "Paths must only contain alphanumeric characters, hyphens (-), "  # noqa: E501
                "underscores (_), and forward slashes (/). Additionally, "
                "paths must not start or end with a forward slash (/)."
            ),
        )
