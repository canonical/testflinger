# Copyright (C) 2022-2025 Canonical
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
"""Testflinger OIDC API."""

import logging
import secrets
from http import HTTPStatus

import requests
from apiflask import APIBlueprint, abort
from flask import jsonify

from testflinger import database
from testflinger.api import auth
from testflinger.oidc import helpers

oidc_api = APIBlueprint("oidc_api", __name__)

logger = logging.getLogger(__name__)

REQUEST_ID_LENGTH = 32


def _exchange_device_code(device_code: str) -> dict:
    """Exchange a device code for tokens at the OIDC token endpoint.

    :param device_code: device code received from the OIDC provider
    :return: parsed JSON response from the OIDC token endpoint
    """
    token_endpoint = helpers.oidc_metadata().get("token_endpoint")
    if not token_endpoint:
        abort(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            message="OIDC provider metadata missing token endpoint",
        )

    try:
        token_response = helpers.oidc_post_request(
            token_endpoint,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": device_code,
            },
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
    except requests.RequestException:
        logger.exception("Failed to reach OIDC token endpoint")
        abort(
            HTTPStatus.BAD_GATEWAY,
            message="Failed to communicate with OIDC provider",
        )

    try:
        return token_response.json()
    except (ValueError, requests.exceptions.JSONDecodeError):
        logger.error(
            "Non-JSON response from OIDC token endpoint (status %s)",
            token_response.status_code,
        )
        abort(
            HTTPStatus.BAD_GATEWAY,
            message="OIDC provider returned an unexpected response",
        )


def _register_and_issue_tokens(userinfo: dict, request_id: str) -> dict:
    """Register an OIDC user and issue Testflinger tokens.

    :param userinfo: user info dict returned by the OIDC provider
    :param request_id: unique request ID used to clean up the device code
    :return: dict containing Testflinger access and refresh tokens
    """
    client_id = userinfo.get("email")
    if not client_id:
        abort(
            HTTPStatus.BAD_GATEWAY,
            message="OIDC provider did not return an email address",
        )

    database.register_oidc_client(userinfo)

    client_permissions = database.get_client_permissions(client_id)
    allowed_resources = {
        permission: value
        for permission, value in client_permissions.items()
        if permission in auth.PERMISSIONS_FIELDS
    }

    # Delete device code after all operations have succeeded
    database.delete_oidc_device_code(request_id)
    return auth.issue_tokens(
        client_id=client_id,
        allowed_resources=allowed_resources,
    )


@oidc_api.post("/auth-init")
def oidc_auth_init() -> dict:
    """Initiate client request and proxy request to OIDC provider.

    :return: dict containing required OIDC parameters for client to
        authenticate with provider
    """
    device_auth_endpoint = helpers.oidc_metadata().get(
        "device_authorization_endpoint"
    )
    if not device_auth_endpoint:
        abort(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            message="OIDC provider does not support device authorization",
        )

    try:
        oidc_response = helpers.oidc_post_request(
            device_auth_endpoint,
            data={"scope": "openid profile email"},
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
    except requests.RequestException:
        logger.exception("Failed to reach OIDC device authorization endpoint")
        abort(
            HTTPStatus.BAD_GATEWAY,
            message="Failed to communicate with OIDC provider",
        )

    if not oidc_response.ok:
        logger.error(
            "OIDC device authorization endpoint returned HTTP %s: %s",
            oidc_response.status_code,
            oidc_response.text,
        )
        abort(
            HTTPStatus.BAD_GATEWAY,
            message="OIDC provider rejected device authorization request",
        )

    try:
        oidc_data = oidc_response.json()
    except (ValueError, requests.exceptions.JSONDecodeError):
        logger.error(
            "Non-JSON response from OIDC device authorization endpoint"
            " (status %s): %s",
            oidc_response.status_code,
            oidc_response.text,
        )
        abort(
            HTTPStatus.BAD_GATEWAY,
            message="OIDC provider returned an unexpected response",
        )

    device_code = oidc_data.pop("device_code", None)
    if not device_code:
        abort(
            HTTPStatus.BAD_GATEWAY,
            message="OIDC provider response missing device_code",
        )

    # Generate unique request ID for client to poll with based on device code
    request_id = secrets.token_urlsafe(REQUEST_ID_LENGTH)

    # Store device code in database with expiration for auth polling
    database.add_oidc_device_code(
        device_code=device_code,
        request_id=request_id,
        expires_in=oidc_data.get("expires_in", 300),
    )

    oidc_data["request_id"] = request_id
    return oidc_data


@oidc_api.post("/auth-poll/<request_id>")
def oidc_auth_poll(request_id: str) -> dict:
    """Poll for OIDC authentication result based on request ID.

    :param request_id: unique request ID generated during auth initiation
    :return: dict containing authentication result and user info if successful
    """
    device_code = database.get_oidc_device_code(request_id)
    if not device_code:
        abort(
            HTTPStatus.BAD_REQUEST,
            message="Invalid or expired request_id",
        )

    idp_token_data = _exchange_device_code(device_code)

    if "error" in idp_token_data:
        error = idp_token_data["error"]
        if error == "authorization_pending":
            return (
                jsonify({"error": "authorization_pending"}),
                HTTPStatus.BAD_REQUEST,
            )
        elif error == "slow_down":
            response = jsonify({"error": "slow_down"})
            response.headers["Retry-After"] = "5"
            response.status_code = HTTPStatus.BAD_REQUEST
            return response
        else:
            database.delete_oidc_device_code(request_id)
            return jsonify({"error": error}), HTTPStatus.BAD_REQUEST

    try:
        userinfo = helpers.oidc_userinfo(idp_token_data["access_token"])
    except (RuntimeError, requests.RequestException):
        logger.exception("Failed to retrieve userinfo from OIDC provider")
        abort(
            HTTPStatus.BAD_GATEWAY,
            message="Failed to retrieve user information from OIDC provider",
        )

    return _register_and_issue_tokens(userinfo, request_id)
