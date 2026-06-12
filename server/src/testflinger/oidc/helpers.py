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
"""Helpers module for OIDC."""

import requests
from authlib.integrations.flask_client import FlaskOAuth2App
from flask import current_app


def oidc_client() -> FlaskOAuth2App:
    """Return the OIDC client from the current app.

    :return: configured OIDC client for the current Flask app
    """
    return current_app.oauth.oidc


def oidc_metadata() -> dict:
    """Return the metadata from the OIDC provider.

    :return: metadata dictionary from the OIDC provider
    """
    return oidc_client().load_server_metadata()


def oidc_post_request(
    url: str,
    data: dict | None = None,
    headers: dict | None = None,
) -> requests.Response:
    """Send a POST request to the OIDC provider with client auth.

    Uses client_secret_basic (Authorization header) for confidential clients.
    Falls back to including client_id in the request body for public clients.

    :param url: URL to send the POST request to
    :param data: optional dictionary of data to include in the request body
    :param headers: optional dictionary of headers to include in the request
    :return: Response object from the POST request
    """
    client_id = oidc_client().client_id
    client_secret = oidc_client().client_secret

    payload = dict(data or {})
    basic_auth = (client_id, client_secret) if client_secret else None
    if not basic_auth:
        payload["client_id"] = client_id

    return requests.post(
        url,
        data=payload,
        auth=basic_auth,
        headers=headers,
        timeout=5,
    )


def oidc_userinfo(access_token: str) -> dict:
    """Retrieve user info from the OIDC provider.

    :param access_token: OIDC access token
    :return: User info as a dictionary
    :raises RuntimeError: if OIDC provider has no userinfo endpoint
    :raises requests.RequestException: on network or HTTP errors
    """
    userinfo_endpoint = oidc_metadata().get("userinfo_endpoint")
    if not userinfo_endpoint:
        raise RuntimeError("OIDC provider has no userinfo endpoint")
    response = requests.get(
        userinfo_endpoint,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=5,
    )
    response.raise_for_status()
    return response.json()
