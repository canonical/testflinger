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

"""Testflinger CLI Auth module."""

import contextlib
from functools import cached_property, wraps
from http import HTTPStatus
from typing import Optional

import jwt

from testflinger_cli import client
from testflinger_cli.errors import AuthenticationError, AuthorizationError


class TestflingerCliAuth:
    """Class to handle authentication and authorisation for Testflinger CLI."""

    def __init__(self, client_id: str, secret_key: str, tf_client):
        self.client_id = client_id
        self.secret_key = secret_key
        self.client = tf_client
        # Fetch JWT token to fail fast in case of any auth error.
        _ = self.jwt_token

    def is_authenticated(self) -> bool:
        """Validate if user is currently authenticated.

        :return: Status for user authentication.
        """
        return self.jwt_token is not None

    @cached_property
    def jwt_token(self) -> str | None:
        """Authenticate with the server and get a JWT."""
        if self.client_id is None or self.secret_key is None:
            return None

        try:
            return self.client.authenticate(self.client_id, self.secret_key)
        except client.HTTPError as exc:
            if exc.status == HTTPStatus.UNAUTHORIZED:
                raise AuthenticationError from exc
            if exc.status == HTTPStatus.FORBIDDEN:
                raise AuthorizationError from exc
        return None

    def build_headers(self) -> Optional[dict]:
        """Create an authorization header based on stored JWT.

        :return: Dict with JWT as the Authorization header if exist.
        """
        return {"Authorization": self.jwt_token} if self.jwt_token else None

    def decode_jwt_token(self) -> Optional[dict]:
        """Decode JWT token without verifying signature.

        This is not for security but for quick screening,
        server will still enforce the JWT token validation.

        :return: Dict with the decoded JWT
        """
        if not self.is_authenticated():
            return None

        try:
            decoded_jwt = jwt.decode(
                self.jwt_token, options={"verify_signature": False}
            )
            return decoded_jwt
        except jwt.exceptions.DecodeError:
            return None

    def refresh_authentication(self) -> None:
        """Attempt to refresh token in case its already expired."""
        del self.jwt_token
        with contextlib.suppress(AuthenticationError, AuthorizationError):
            _ = self.jwt_token

    def get_user_role(self) -> str:
        """Retrieve the role for the user from the decoded jwt.

        :return: String with the role, defaults to 'user' if not authenticated.
        """
        decoded_token = self.decode_jwt_token()
        if not decoded_token:
            return "user"

        permissions = decoded_token.get("permissions", {})
        # If there is a decoded token, the user was authenticated
        # Default role for legacy client_ids is contributor
        return permissions.get("role", "contributor")


def require_role(*roles):
    """Determine if a user is entitled to perform CLI action."""

    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            auth = self.main_cli.auth

            if not auth.is_authenticated():
                raise AuthenticationError
            user_role = auth.get_user_role()
            if user_role not in roles:
                raise AuthorizationError(
                    f"Authorization Error: Command requires role: {roles}"
                )

            return func(self, *args, **kwargs)

        return wrapper

    return decorator
