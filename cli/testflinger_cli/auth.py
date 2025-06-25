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
        self._jwt_token = None
        self._authenticate_with_server()

    def is_authenticated(self) -> bool:
        """Validate if user is currently authenticated.

        :return: Status for user authentication.
        """
        return self._jwt_token is not None

    def _authenticate_with_server(self) -> None:
        """
        Authenticate client id and secret key with server
        and store JWT with permissions.
        """
        if self.client_id is None or self.secret_key is None:
            return None

        try:
            self._jwt_token = self.client.authenticate(
                self.client_id, self.secret_key
            )
        except client.HTTPError as exc:
            if exc.status == HTTPStatus.UNAUTHORIZED:
                raise AuthenticationError from exc
            elif exc.status == HTTPStatus.FORBIDDEN:
                raise AuthorizationError from exc

    def build_headers(self) -> Optional[dict]:
        """Create an authorization header based on stored JWT.

        :return: Dict with JWT as the Authorization header if exist.
        """
        return {"Authorization": self._jwt_token} if self._jwt_token else None

    def decode_jwt_token(self) -> Optional[dict]:
        """Decode JWT token without verifying signature.
        This is not for security but for quick screening,
        server will still enforce the JWT token validation.

        :return: Dict with the decoded JWT
        """
        if self.is_authenticated():
            decoded_jwt = jwt.decode(
                self._jwt_token, options={"verify_signature": False}
            )
            return decoded_jwt
        return None

    def refresh_authentication(self) -> None:
        """Attempt to refresh token in case its already expired."""
        self._authenticate_with_server()

    def get_user_role(self) -> str:
        """Retrieve the role for the user from the decoded jwt.

        :return: String with the role, defaults to 'user' if not authenticated.
        """
        decoded_token = self.decode_jwt_token()
        if not decoded_token:
            return "user"

        permissions = decoded_token.get("permissions", {})

        # If there is a decoded token, the user was authenticated
        # Default role for legacy client_id's is contributor
        return permissions.get("role", "contributor")
