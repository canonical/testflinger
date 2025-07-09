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

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from apiflask import abort

from testflinger import database


def validate_client_key_pair(client_id: str, client_key: str) -> dict:
    """
    Check credentials for validity and returns their permissions.

    :param client_id: user to validate crendentials from.
    :param client_key: password for the authenticated user.
    :return: entry with all permissions allowed for a user.
    """
    if client_key is None:
        return None
    client_key_bytes = client_key.encode("utf-8")
    client_permissions_entry = database.get_client_permissions(client_id)

    if client_permissions_entry is None or not bcrypt.checkpw(
        client_key_bytes,
        client_permissions_entry["client_secret_hash"].encode("utf8"),
    ):
        return None
    client_permissions_entry.pop("_id", None)
    client_permissions_entry.pop("client_secret_hash", None)
    return client_permissions_entry


def generate_token(allowed_resources: dict, secret_key: str) -> str:
    """
    Generate JWT token with queue permission given a secret key.

    :param allowed_resources: dictionary with all permissions for a user
    :secret_key: Signing key to set the authenticity of the token.

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


def decode_jwt_token(auth_token: str, secret_key: str) -> dict:
    """
    Decode authorization token using the secret key. Aborts with
    an HTTP error if it does not exist or if it fails to decode.

    :param auth_token: JWT token with all permissions
    :secret_key: Signing key to validate the authenticity of the token.
    :return: Dictionary with the information decoded from the JWT token.
    """
    if auth_token is None:
        abort(401, "Unauthorized")
    try:
        decoded_jwt = jwt.decode(
            auth_token,
            secret_key,
            algorithms="HS256",
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.exceptions.ExpiredSignatureError:
        abort(401, "Token has expired")
    except jwt.exceptions.InvalidTokenError:
        abort(403, "Invalid Token")

    return decoded_jwt


def check_token_priority(
    auth_token: str, secret_key: str, queue: str, priority: int
) -> bool:
    """
    Check if the requested priority is less than the max priority
    specified in the authorization token if it exists.

    :param auth_token: JWT token with all permissions
    :secret_key: Signing key to validate the authenticity of the token.
    :queue: Queue name defined in the job.
    :priority: Priority defined in the job.
    """
    if priority == 0:
        return
    decoded_jwt = decode_jwt_token(auth_token, secret_key)
    permissions = decoded_jwt.get("permissions", {})
    max_priority_dict = permissions.get("max_priority", {})
    star_priority = max_priority_dict.get("*", 0)
    queue_priority = max_priority_dict.get(queue, 0)
    max_priority = max(star_priority, queue_priority)
    if priority > max_priority:
        abort(
            403,
            (
                f"Not enough permissions to push to {queue} "
                f"with priority {priority}"
            ),
        )


def check_token_queue(auth_token: str, secret_key: str, queue: str) -> bool:
    """
    Check if the queue is in the restricted list.

    If queue is restricted checks the authorization token for restricted
    queues the user is allowed to use.

    :param auth_token: JWT token with all permissions
    :secret_key: Signing key to validate the authenticity of the token.
    :queue: Queue name defined in the job.
    """
    if not database.check_queue_restricted(queue):
        return
    decoded_jwt = decode_jwt_token(auth_token, secret_key)
    permissions = decoded_jwt.get("permissions", {})
    allowed_queues = permissions.get("allowed_queues", [])
    if queue not in allowed_queues:
        abort(
            403,
            (
                "Not enough permissions to push to the "
                f"restricted queue: {queue}"
            ),
        )


def check_token_reservation_timeout(
    auth_token: str, secret_key: str, reservation_timeout: int, queue: str
) -> bool:
    """
    Check if the requested reservation is either less than the max
    or that their token gives them the permission to use a higher one.

    :param auth_token: JWT token with all permissions
    :secret_key: Signing key to validate the authenticity of the token.
    :reservation_timeout: Timeout defined in job.
    :queue: Queue name defined in the job.
    """
    # Max reservation time defaults to 6 hours
    max_reservation_time = 6 * 60 * 60
    if reservation_timeout <= max_reservation_time:
        return
    decoded_jwt = decode_jwt_token(auth_token, secret_key)
    permissions = decoded_jwt.get("permissions", {})
    max_reservation_time_dict = permissions.get("max_reservation_time", {})
    queue_reservation_time = max_reservation_time_dict.get(queue, 0)
    star_reservation_time = max_reservation_time_dict.get("*", 0)
    max_reservation_time = max(queue_reservation_time, star_reservation_time)
    if reservation_timeout > max_reservation_time:
        abort(
            403,
            (
                f"Not enough permissions to push to {queue} "
                f"with reservation timeout {reservation_timeout}"
            ),
        )


def check_token_permissions(
    auth_token: str, secret_key: str, job_data: dict
) -> bool:
    """
    Validate token received from client and checks if it can
    push a job to the queue with the requested priority.
    """
    priority_level = job_data.get("job_priority", 0)
    job_queue = job_data["job_queue"]
    check_token_priority(auth_token, secret_key, job_queue, priority_level)
    check_token_queue(auth_token, secret_key, job_queue)

    reserve_data = job_data.get("reserve_data", {})
    # Default reservation timeout is 1 hour
    reservation_timeout = reserve_data.get("timeout", 3600)
    check_token_reservation_timeout(
        auth_token, secret_key, reservation_timeout, job_queue
    )
