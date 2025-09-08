# Copyright (C) 2020-2022 Canonical
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

"""Testflinger API Auth module."""

import os
from datetime import datetime, timedelta, timezone
from functools import wraps
from http import HTTPStatus

import bcrypt
import jwt
from apiflask import abort
from authlib.common.security import generate_token
from flask import g, request

from testflinger import database
from testflinger.enums import ServerRoles


def validate_client_key_pair(
    client_id: str | None, client_key: str | None
) -> dict | None:
    """
    Check credentials for validity and returns their permissions.

    :param client_id: user to validate crendentials from.
    :param client_key: password for the authenticated user.
    :return: entry with all permissions allowed for a user.
    """
    if not client_id:
        return None
    client_key_bytes = client_key.encode("utf-8")
    client_permissions_entry = database.get_client_permissions(client_id)

    if client_permissions_entry is None or not bcrypt.checkpw(
        client_key_bytes,
        client_permissions_entry["client_secret_hash"].encode("utf8"),
    ):
        return None
    # Removing client_secret_hash for security purposes
    client_permissions_entry.pop("client_secret_hash", None)
    return client_permissions_entry


def generate_access_token(allowed_resources: dict, secret_key: str) -> str:
    """
    Generate JWT access token with queue permission given a secret key.

    :param allowed_resources: dictionary with all permissions for a user
    :param secret_key: Signing key to set the authenticity of the token.

    :return: JWT token with all user permissions.
    """
    expiration_time = datetime.now(timezone.utc) + timedelta(seconds=30)
    token_payload = {
        "exp": expiration_time,
        "iat": datetime.now(timezone.utc),  # Issued at time
        "sub": "access_token",
        "permissions": allowed_resources,
    }
    token = jwt.encode(token_payload, secret_key, algorithm="HS256")
    return token


def decode_jwt_token(auth_token: str | None, secret_key: str) -> dict | None:
    """
    Decode authorization token using the secret key. Aborts with
    an HTTP error if it does not exist or if it fails to decode.

    :param auth_token: JWT token with all permissions
    :param secret_key: Signing key to validate the authenticity of the token.
    :return: Dictionary with the information decoded from the JWT token.
    """
    if not auth_token:
        abort(HTTPStatus.UNAUTHORIZED, "Unauthorized")
    try:
        decoded_jwt = jwt.decode(
            auth_token,
            secret_key,
            algorithms="HS256",
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.exceptions.ExpiredSignatureError:
        abort(HTTPStatus.UNAUTHORIZED, "Token has expired")
    except jwt.exceptions.InvalidTokenError:
        abort(HTTPStatus.FORBIDDEN, "Invalid Token")

    return decoded_jwt


def check_max_priority(permissions: dict, queue: str, priority: int) -> None:
    """
    Check if the requested priority is less than the max priority
    specified in the authorization token if it exists.

    :param permissions: Permissions given to user.
    :param queue: Queue name defined in the job.
    :param priority: Priority defined in the job.
    """
    # No auth required if priority is set to 0 mandatory otherwise
    if priority == 0:
        return

    # If no permissions found it means user is not authenticated
    if not permissions:
        abort(
            HTTPStatus.UNAUTHORIZED,
            f"Authentication required for setting priority: {priority}",
        )

    max_priority_dict = permissions.get("max_priority", {})
    star_priority = max_priority_dict.get("*", 0)
    queue_priority = max_priority_dict.get(queue, 0)
    max_priority = max(star_priority, queue_priority)
    if priority > max_priority:
        abort(
            HTTPStatus.FORBIDDEN,
            (
                f"Not enough permissions to push to {queue} "
                f"with priority {priority}"
            ),
        )


def check_queue_restriction(permissions: dict, queue: str) -> None:
    """
    Check if the queue is in the restricted list.

    If queue is restricted checks the authorization token for restricted
    queues the user is allowed to use.

    :param permissions: Permissions given to user.
    :param queue: Queue name defined in the job.
    """
    # No auth required if queue is not restricted mandatory otherwise
    if not database.check_queue_restricted(queue):
        return

    # If no permissions found it means user is not authenticated
    if not permissions:
        abort(
            HTTPStatus.UNAUTHORIZED,
            f"Authentication required to push to restricted queue: {queue}",
        )

    allowed_queues = permissions.get("allowed_queues", [])
    if queue not in allowed_queues:
        abort(
            HTTPStatus.FORBIDDEN,
            (
                "Not enough permissions to push to the "
                f"restricted queue: {queue}"
            ),
        )


def check_max_reservation_timeout(
    permissions: dict, reservation_timeout: int, queue: str
) -> None:
    """
    Check if the requested reservation is either less than the max
    or that their token gives them the permission to use a higher one.

    :param permissions: Permissions given to user.
    :param reservation_timeout: Timeout defined in job.
    :param queue: Queue name defined in the job.
    """
    # Max reservation time defaults to 6 hours
    max_reservation_time = 6 * 60 * 60
    # No auth required if reservation less than 6hrs mandatory otherwise
    if reservation_timeout <= max_reservation_time:
        return

    # If no permissions found it means user is not authenticated
    if not permissions:
        abort(
            HTTPStatus.UNAUTHORIZED,
            (
                "Authentication required for setting "
                f"timeout: {reservation_timeout}"
            ),
        )

    max_reservation_time_dict = permissions.get("max_reservation_time", {})
    queue_reservation_time = max_reservation_time_dict.get(queue, 0)
    star_reservation_time = max_reservation_time_dict.get("*", 0)
    max_reservation_time = max(queue_reservation_time, star_reservation_time)
    if reservation_timeout > max_reservation_time:
        abort(
            HTTPStatus.FORBIDDEN,
            (
                f"Not enough permissions to push to {queue} "
                f"with reservation timeout {reservation_timeout}"
            ),
        )


def check_permissions(permissions: dict, job_data: dict) -> None:
    """
    Validate token received from client and checks if it can
    push a job to the queue with the requested priority.
    """
    priority_level = job_data.get("job_priority", 0)
    job_queue = job_data["job_queue"]
    check_max_priority(permissions, job_queue, priority_level)
    check_queue_restriction(permissions, job_queue)

    reserve_data = job_data.get("reserve_data", {})
    # Default reservation timeout is 1 hour
    reservation_timeout = reserve_data.get("timeout", 3600)
    check_max_reservation_timeout(permissions, reservation_timeout, job_queue)


def authenticate(func):
    """Attempt authentication if token provided and store auth variables."""

    @wraps(func)
    def decorator(*args, **kwargs):
        # Retrieve authentication header
        auth_token = request.headers.get("Authorization")

        # Initialize auth state
        g.client_id = None
        g.role = ServerRoles.USER
        g.permissions = {}
        g.is_authenticated = False

        # If no token, continuing as regular user.
        if not auth_token:
            return func(*args, **kwargs)

        if auth_token.startswith("Bearer "):
            auth_token = auth_token[len("Bearer ") :]

        # If there is a token available, attempt to retrieve information
        secret_key = os.environ.get("JWT_SIGNING_KEY")
        decoded_jwt = decode_jwt_token(auth_token, secret_key)
        permissions = decoded_jwt.get("permissions", {})

        # Store auth state if decoding was successful
        g.client_id = permissions["client_id"]
        g.role = permissions.get("role", ServerRoles.CONTRIBUTOR)
        g.permissions = permissions
        g.is_authenticated = True

        return func(*args, **kwargs)

    return decorator


def require_role(*roles):
    """Determine if a user is entitled to do a request on endpoint."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not g.is_authenticated:
                abort(
                    HTTPStatus.UNAUTHORIZED,
                    "Authentication is required for specified endpoint",
                )

            if g.role not in roles:
                role_list = ", ".join(r.value for r in roles)
                abort(
                    HTTPStatus.FORBIDDEN,
                    f"Specified action requires role: {role_list}",
                )

            return func(*args, **kwargs)

        return wrapper

    return decorator


def check_role_hierarchy(user_role: str, target_role: str) -> bool:
    """
    Check role of current user to validate if authorized to perform action.

    :param user_role: Role of the user making the request.
    :param target_role: Role being assigned or modified.
    :return: True if allowed, False otherwise.
    """
    role_levels = {
        ServerRoles.USER: 1,
        ServerRoles.CONTRIBUTOR: 2,
        ServerRoles.MANAGER: 3,
        ServerRoles.ADMIN: 4,
    }

    current_level = role_levels.get(user_role, 0)
    target_level = role_levels.get(target_role, 0)

    # Users can modify roles at their level or below
    return current_level >= target_level


def generate_refresh_token(client_id: str, expires_in: int | None) -> str:
    """
    Generate opaque string as a new refresh token.

    :param client_id: Client ID associated with this refresh token.
    :param expires_in: Expiration time in seconds (default 30 days).
                       Set to None for non-expiring token.

    :return: Refresh token string.
    """
    refresh_token = generate_token(48)  # equal to 64 char
    now = datetime.now(timezone.utc)
    token_data = {
        "client_id": client_id,
        "refresh_token": refresh_token,
        "issued_at": now,
        "expires_at": None
        if expires_in is None
        else now + timedelta(seconds=expires_in),
        "revoked": False,
        "last_accessed": now,
    }
    database.add_refresh_token(token_data)
    return refresh_token


def validate_refresh_token(token: str) -> dict:
    """
    Validate refresh token existence, revocation and expiration.

    :param token: Refresh token string.

    :return: Token entry from DB if valid.
    """
    token_entry = database.get_refresh_token_by_token(token)
    if not token_entry:
        abort(HTTPStatus.BAD_REQUEST, "Invalid refresh token.")

    if token_entry["revoked"]:
        abort(HTTPStatus.BAD_REQUEST, "Refresh token revoked.")

    expires_at = token_entry.get("expires_at")
    if expires_at:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at < datetime.now(timezone.utc):
            abort(HTTPStatus.BAD_REQUEST, "Refresh token expired")

    database.edit_refresh_token(
        token_entry["refresh_token"],
        {"last_accessed": datetime.now(timezone.utc)},
    )

    return token_entry
