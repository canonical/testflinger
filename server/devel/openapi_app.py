# Copyright (C) 2025 Canonical
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

"""
Minimal Flask application for OpenAPI specification generation.

This module creates a lightweight Testflinger server instance specifically
for extracting the OpenAPI specification without requiring MongoDB or other
external dependencies. 
It's used by the APIFlask to generate the API spec in JSON format. 
(https://apiflask.com/openapi/#the-flask-spec-command)

Usage:
    uvx --with tox-uv tox -e schema
"""

from dataclasses import dataclass 
from testflinger.application import create_flask_app

@dataclass
class OpenAPIConfig:
    """Config for Testing."""

    TESTING = True

# Create and expose the app in TESTING mode for Flask CLI to use
app = create_flask_app(OpenAPIConfig)
