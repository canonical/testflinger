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

import configparser
import contextlib
from functools import cached_property, wraps
from http import HTTPStatus
from typing import Optional

import jwt
from xdg_base_dirs import xdg_config_home

from testflinger_cli import client
from testflinger_cli.consts import ServerRoles
from testflinger_cli.errors import (
    AuthenticationError,
    AuthorizationError,
    InvalidTokenError,
)


class TestflingerCliAuth:
    """Class to handle authentication and authorisation for Testflinger CLI."""

    def __init__(self, client_id: str, secret_key: str, tf_client):
        self.client_id = client_id
        self.secret_key = secret_key
        self.client = tf_client

        # Refresh token relevant configuration
        config_home = xdg_config_home()
        config_home.mkdir(parents=True, exist_ok=True)
        self.auth_config = config_home / "testflinger-cli-auth.conf"

    def is_authenticated(self) -> bool:
        """Validate if user is currently authenticated.

        :return: Status for user authentication.
        """
        return self.jwt_token is not None

    def authenticate(self) -> str | None:
        """Authenticate with server and retrieve access and refresh tokens.

        Authentication can be made via explicit command line arguments,
        environment variables or refresh token in that order of priority.

        :raises AuthenticationError: Invalid credentials were provided
        :raises AuthorizationError: User is not authorized
        :raises InvalidTokenError: Refresh token already expired
        :return: string with access token (jwt token)
        """
        # Authenticate with credentials if provided in args or env file
        if self.client_id and self.secret_key:
            return self._authenticate_with_credentials()

        # Authenticate with refresh token if available
        refresh_token = self.get_stored_refresh_token()
        if refresh_token:
            return self._authenticate_with_refresh_token(refresh_token)

        return None

    def _authenticate_with_credentials(self) -> str:
        """Authenticate using client_id and secret_key."""
        try:
            response = self.client.authenticate(
                self.client_id, self.secret_key
            )
            # Store refresh token for persistent login
            self.store_refresh_token(response["refresh_token"])
            return response["access_token"]
        except client.HTTPError as exc:
            self._handle_auth_error(exc)

    def _authenticate_with_refresh_token(self, refresh_token: str) -> str:
        """Authenticate using stored refresh token."""
        try:
            response = self.client.refresh_authentication(refresh_token)
            return response["access_token"]
        except client.HTTPError as exc:
            if exc.status == HTTPStatus.BAD_REQUEST:
                self.clear_refresh_token()
                raise InvalidTokenError(exc.msg) from exc
            self._handle_auth_error(exc)

    def _handle_auth_error(self, exc: client.HTTPError) -> None:
        """Handle authentication HTTP errors."""
        if exc.status == HTTPStatus.UNAUTHORIZED:
            raise AuthenticationError from exc
        if exc.status == HTTPStatus.FORBIDDEN:
            raise AuthorizationError from exc

    @cached_property
    def jwt_token(self) -> str | None:
        """Authenticate with the server and get a JWT."""
        return self.authenticate()

    def get_stored_refresh_token(self) -> str | None:
        """Retrieve the refresh token from SNAP_USER_DATA.

        :return: refresh token if any, otherwise None
        """
        config_file = configparser.ConfigParser()
        try:
            config_file.read(self.auth_config)
        except FileNotFoundError:
            return None

        # Set client_id from config file to keep token owner
        self.client_id = config_file.get("AUTH", "client_id", fallback=None)
        return config_file.get("AUTH", "refresh_token", fallback=None)

    def store_refresh_token(self, refresh_token: str) -> None:
        """Store refresh token for persistent login.

        :param refresh_token: refresh token to store in SNAP_USER_DATA
        """
        config_file = configparser.ConfigParser()
        config_file["AUTH"] = {
            "client_id": self.client_id,
            "refresh_token": refresh_token,
        }
        try:
            with self.auth_config.open("w") as file:
                config_file.write(file)
        except (OSError, PermissionError):
            # Ignore write errors as this might run as non snap
            pass

    def clear_refresh_token(self):
        """Cleanup refresh_token if already expired or revoked."""
        if self.auth_config.exists():
            try:
                self.auth_config.unlink()
            except (OSError, PermissionError):
                # Empty file if unable to remove it
                with self.auth_config.open("w"):
                    pass

    def build_headers(self) -> Optional[dict]:
        """Create an authorization header based on stored JWT.

        :return: Dict with JWT as the Authorization header if exist.
        """
        return (
            {"Authorization": f"Bearer {self.jwt_token}"}
            if self.jwt_token
            else None
        )

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
            return ServerRoles.USER

        permissions = decoded_token.get("permissions", {})
        # If there is a decoded token, the user was authenticated
        # Default role for legacy client_ids is contributor
        return permissions.get("role", ServerRoles.CONTRIBUTOR)


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
                role_list = ", ".join(r.value for r in roles)
                raise AuthorizationError(
                    f"Authorization Error: Command requires role: {role_list}"
                )

            return func(self, *args, **kwargs)

        return wrapper

    return decorator
