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

import base64
import configparser
import re
import sys
import time
import urllib.parse
import webbrowser
from functools import cached_property, wraps
from http import HTTPStatus
from pathlib import Path
from typing import Optional

import jwt
import requests
from xdg_base_dirs import xdg_config_home

from testflinger_cli.enums import ServerRoles
from testflinger_cli.errors import (
    AuthenticationError,
    AuthorizationError,
    InvalidTokenError,
    NetworkError,
    OidcError,
)

DEFAULT_AUTH_TIMEOUT = 15  # seconds


class TestflingerCliAuth:
    """Class to handle authentication and authorisation for Testflinger CLI."""

    def __init__(
        self,
        server_url: str,
        client_id: str | None = None,
        secret_key: str | None = None,
    ):
        """Initialize the Testflinger CLI Auth class."""
        self.server_url = server_url
        self.client_id = client_id
        self.secret_key = secret_key

        # Refresh token relevant configuration
        self.config_home = xdg_config_home() / "testflinger-cli"
        self.config_home.mkdir(parents=True, exist_ok=True)

    @cached_property
    def auth_config(self):
        """Return the path to the auth config file that is in use."""
        print("Establishing cached value for auth_config based on:")
        print(f"server_url: {self.server_url}")
        print(f"client_id: {self.client_id}")

        # Also support multiple server combinations, staging and production,
        # as each will have different refresh tokens
        auth_config = self.config_home / self._safe_fs_name(self.server_url)

        # When the client is known, we must only use refresh tokens that are
        # also for that client_id.
        if self.client_id:
            auth_config /= self._safe_fs_name(self.client_id)
        # When the client_id isn't known, we will try to use the last refresh
        # token for that server. In turn that will resolve the client_id.

        # This means that we can only differentiate which token to use based
        # on the server, when no client_id is known. This means that we must
        # save the config file for the server (always) and for the specific
        # client_id (also) when available.

        auth_config /= ("auth.conf")
        print(f"The resulting auth_config:\n{auth_config}", file=sys.stderr)
        auth_config.parent.mkdir(parents=True, exist_ok=True)
        try:
            with auth_config.open("r") as f:
                for line in f:
                    print(line)
            config_file = configparser.ConfigParser()
            config_file.read(auth_config)
            print(vars(config_file))
        except:
            pass

        return auth_config

    @staticmethod
    def _safe_fs_name(name_in: str) -> str:
        """Return a folder name that is reduced to valid characters."""
        return re.sub(r"([^a-zA-Z0-9_]+)", "_", name_in)

    def get_url(self, endpoint: str) -> str:
        """Construct the full URL for a given endpoint.

        :param endpoint: The endpoint to construct the URL for.
        :return: The full URL for the given endpoint.
        """
        return urllib.parse.urljoin(self.server_url, endpoint)

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
        # 1. Attempt to authenticate with credentials from args or envvars
        # Higher priority to honor users intent when credentials present
        if self.client_id and self.secret_key:
            print("authenticate #1")
            return self._authenticate_with_credentials()

        # 2. Authenticate with refresh token if available
        # This covers persistent login for both credentials and OIDC logins
        refresh_token = self.get_stored_refresh_token()
        token_expired: InvalidTokenError | None = None
        if refresh_token:
            try:
                print("authenticate #2")
                return self._authenticate_with_refresh_token(refresh_token)
            except InvalidTokenError as exc:
                token_expired = exc

        # 3. Authenticate with OIDC if no credentials or refresh token
        # This should fail gracefully if OIDC is not enabled on the server
        access_token = self._authenticate_with_oidc()
        if not access_token and token_expired:
            print("authenticate #3")
            # If neither authentication method worked and refresh token invalid
            # raise the InvalidTokenError to force reauthentication
            raise token_expired
        return access_token

    def _authenticate_with_credentials(self) -> str | None:
        """Authenticate using client_id and secret_key.

        :return: string with access token (jwt token)
        """
        url = self.get_url("/v1/oauth2/token")
        id_key_pair = f"{self.client_id}:{self.secret_key}"
        encoded_id_key_pair = base64.b64encode(
            id_key_pair.encode("utf-8")
        ).decode("ascii")
        headers = {"Authorization": f"Basic {encoded_id_key_pair}"}

        try:
            response = requests.post(
                url, {}, headers=headers, timeout=DEFAULT_AUTH_TIMEOUT
            )
            response.raise_for_status()
            response_data = response.json()
        except requests.exceptions.HTTPError as exc:
            self._handle_auth_error(exc)
            return None
        except requests.exceptions.Timeout as exc:
            raise NetworkError(
                "Connection to testflinger server timed out while "
                "authenticating with basic client_id+secret_key credentials."
            ) from exc

        # Store refresh token for persistent login
        self.store_refresh_token(response_data["refresh_token"])
        return response_data["access_token"]

    def _authenticate_with_refresh_token(
        self, refresh_token: str
    ) -> str | None:
        """Authenticate using stored refresh token.

        :param refresh_token: refresh token to use for authentication
        :return: string with access token (jwt token)
        """
        url = self.get_url("/v1/oauth2/refresh")

        try:
            response = requests.post(
                url,
                json={"refresh_token": refresh_token},
                timeout=DEFAULT_AUTH_TIMEOUT,
            )
            response.raise_for_status()
            response_data = response.json()
            return response_data["access_token"]
        except requests.exceptions.HTTPError as exc:
            if exc.response.status_code == HTTPStatus.BAD_REQUEST:
                self.clear_refresh_token()
                raise InvalidTokenError(
                    "Invalid or expired refresh token."
                ) from exc

            self._handle_auth_error(exc)
            return None
        except requests.exceptions.Timeout as exc:
            raise NetworkError(
                "Connection timed out while refreshing authentication token."
            ) from exc

    def _handle_auth_error(self, exc: requests.exceptions.HTTPError) -> None:
        """Handle authentication HTTP errors."""
        if exc.response.status_code == HTTPStatus.UNAUTHORIZED:
            raise AuthenticationError from exc
        if exc.response.status_code == HTTPStatus.FORBIDDEN:
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
            print("get_stored_refresh_token")
            config_file.read(self.auth_config)
        except FileNotFoundError:
            print(f"no stored refresh token in {self.auth_config}")
            return None

        # Set client_id from config file to keep token owner
        self.client_id = config_file.get("AUTH", "client_id", fallback=None)
        return config_file.get("AUTH", "refresh_token", fallback=None)

    def store_refresh_token(self, refresh_token: str) -> None:
        """Store refresh token for persistent login.

        :param refresh_token: refresh token to store in SNAP_USER_DATA
        """
        if self.client_id and refresh_token:
            config_file = configparser.ConfigParser()
            config_file["AUTH"] = {
                "client_id": self.client_id,
                "refresh_token": refresh_token,
            }
            try:
                orig = self.auth_config
                print("store_refresh_token to ...")
                print(f"{self.auth_config}")
                with self.auth_config.open("w") as file:
                    config_file.write(file)

                # Note: if client_id wasn't part of that file path, we should
                # write another client-id-pathed refresh file
                del self.auth_config
                if self.auth_config != orig:
                    print("Also store_refresh_token based on client_id too!")
                    print(f"{self.auth_config}")
                    with self.auth_config.open("w") as file:
                        config_file.write(file)
            except (OSError, PermissionError):
                # Ignore write errors as this might run as non snap
                print ("why are we ignoring write errors?")
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

    def build_headers(self) -> dict:
        """Create an authorization header based on stored JWT.

        :return: Dict with JWT as the Authorization header if exist.
        """
        return (
            {"Authorization": f"Bearer {self.jwt_token}"}
            if self.jwt_token
            else {}
        )

    def decode_jwt_token(self, token: str | None = None) -> Optional[dict]:
        """Decode JWT token without verifying signature.

        This is not for security but for quick screening,
        server will still enforce the JWT token validation.

        :param token: optional token to decode, defaults to self.jwt_token
        :return: Dict with the decoded JWT
        """
        token_to_decode = token or self.jwt_token
        if not token_to_decode:
            return None

        try:
            return jwt.decode(
                token_to_decode, options={"verify_signature": False}
            )
        except jwt.exceptions.DecodeError:
            return None

    def refresh_authentication(self) -> None:
        """Re-acquire the access token, raising on failure."""
        del self.jwt_token
        _ = self.jwt_token

    def get_user_role(self) -> str | None:
        """Retrieve the role for the user from the decoded jwt.

        :return: String with the role, return None if not authenticated.
        """
        decoded_token = self.decode_jwt_token()
        if not decoded_token:
            return None

        permissions = decoded_token.get("permissions", {})
        # If there is a decoded token, the user was authenticated
        # Default role for legacy client_ids is contributor
        return permissions.get("role", ServerRoles.CONTRIBUTOR)

    def _authenticate_with_oidc(self) -> str | None:
        """Authenticate using OIDC device flow."""
        auth_init_url = self.get_url("/oidc/auth-init")

        try:
            response = requests.post(
                auth_init_url, data={}, timeout=DEFAULT_AUTH_TIMEOUT
            )
            response.raise_for_status()
            init_data = response.json()
        except requests.exceptions.HTTPError as exc:
            if exc.response.status_code == HTTPStatus.NOT_FOUND:
                # Server does not have OIDC enabled
                # Need to return None to fail gracefully
                return None

            raise OidcError(f"Failed to initiate OIDC login: {exc}") from exc
        except requests.exceptions.Timeout as exc:
            raise NetworkError(
                "Connection timed out while initiating OIDC login."
            ) from exc

        verification_uri = init_data["verification_uri"]
        user_code = init_data["user_code"]
        interval = init_data.get("interval", 5)
        expires_in = init_data.get("expires_in", 300)
        request_id = init_data["request_id"]

        print(
            f"Please visit {verification_uri} and enter code "
            f"{user_code} to login.",
            file=sys.stderr
        )

        # Attempt to launch the browser for the user to login
        webbrowser.open(verification_uri)

        code_expiration = time.monotonic() + expires_in
        while time.monotonic() < code_expiration:
            time.sleep(interval)
            poll_url = self.get_url(f"/oidc/auth-poll/{request_id}")
            try:
                response = requests.post(
                    poll_url, data={}, timeout=DEFAULT_AUTH_TIMEOUT
                )
                response.raise_for_status()
                auth_data = response.json()
                decoded = self.decode_jwt_token(auth_data["access_token"])
                self.client_id = (
                    decoded.get("permissions", {}).get("client_id")
                    if decoded
                    else None
                )
                if self.client_id:
                    self.store_refresh_token(auth_data["refresh_token"])
                return auth_data["access_token"]
            except requests.exceptions.HTTPError as exc:
                error_data = exc.response.json()
                match error_data.get("error"):
                    case "authorization_pending":
                        pass
                    case "slow_down":
                        interval += int(
                            exc.response.headers.get("Retry-After", 5)
                        )
                    case "access_denied":
                        raise OidcError(
                            "Authentication failed: access denied"
                        ) from exc
                    case "expired_token":
                        raise OidcError(
                            "Authentication timed out. Please try again."
                        ) from exc
                    case _:
                        raise OidcError(
                            "Unexpected error during OIDC "
                            f"authentication: {exc}"
                        ) from exc
            except requests.exceptions.Timeout as exc:
                raise NetworkError(
                    "Connection timed out while authenticating with OIDC."
                ) from exc

        raise OidcError("Authentication timed out. Please try again.")


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
