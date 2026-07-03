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
"""Fixtures for testing."""

import base64
import os
from datetime import datetime, timedelta, timezone
from http import HTTPStatus

import jwt
from testflinger_common.enums import ServerRoles


def get_access_token_header(client_id: str, role: ServerRoles) -> dict:
    """Create a Bearer token header for the specified role."""
    secret_key = os.environ.get("JWT_SIGNING_KEY")
    expiration_time = datetime.now(timezone.utc) + timedelta(seconds=30)
    token_payload = {
        "exp": expiration_time,
        "iat": datetime.now(timezone.utc),
        "sub": "access_token",
        "permissions": {
            "client_id": client_id,
            "role": role,
            # not implemented: queues, time extensions, etc.
        },
    }
    token = jwt.encode(token_payload, secret_key, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def get_basic_auth_header(client_id: str, client_key: str) -> dict:
    """Create HTTP Basic auth header from client credentials."""
    id_pair = f"{client_id}:{client_key}"
    encoded = base64.b64encode(id_pair.encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {encoded}"}


def get_access_token(app, client_id, client_key):
    """
    Authenticate and return a valid access token.
    Note: app must already be aware of client_id's existence.
    """
    response = app.post(
        "/v1/oauth2/token",
        headers=get_basic_auth_header(client_id, client_key),
    )
    assert response.status_code == HTTPStatus.OK, (
        f"{response.status} {response.data}"
    )
    return response.get_json()["access_token"]


def get_refresh_token(app, client_id, client_key):
    """
    Authenticate and return a valid refresh token.
    Note: app must already be aware of client_id's existence.
    """
    response = app.post(
        "/v1/oauth2/token",
        headers=get_basic_auth_header(client_id, client_key),
    )
    assert response.status_code == HTTPStatus.OK, (
        f"{response.status} {response.data}"
    )
    return response.get_json()["refresh_token"]
