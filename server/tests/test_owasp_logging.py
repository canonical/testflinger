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
#
"""
Unit tests for OWASP logging across authentication and authorization
events in the Testflinger API.
"""

import base64
import logging
from http import HTTPStatus

import bcrypt
import pytest
from testflinger_common.enums import ServerRoles


def create_auth_header(client_id: str, client_key: str) -> dict:
    """Create authorization header with base64 encoded credentials."""
    id_key_pair = f"{client_id}:{client_key}"
    base64_encoded = base64.b64encode(id_key_pair.encode("utf-8")).decode()
    return {"Authorization": f"Basic {base64_encoded}"}


def get_access_token(app, client_id: str, client_key: str) -> str:
    """Authenticate and return a valid JWT access token."""
    response = app.post(
        "/v1/oauth2/token",
        headers=create_auth_header(client_id, client_key),
    )
    return response.get_json()["access_token"]


# Define endpoints by required role for parametrized testing
ADMIN_ONLY_ENDPOINTS = [
    ("/v1/oauth2/revoke", "POST"),
    ("/v1/client-permissions/test_client", "DELETE"),
]

ADMIN_MANAGER_ENDPOINTS = [
    ("/v1/client-permissions", "GET"),
    ("/v1/client-permissions/test_client", "GET"),
    ("/v1/client-permissions/test_client", "PUT"),
    ("/v1/restricted-queues/test_queue", "POST"),
    ("/v1/restricted-queues/test_queue", "DELETE"),
]

ADMIN_MANAGER_CONTRIBUTOR_ENDPOINTS = [
    ("/v1/restricted-queues", "GET"),
    ("/v1/restricted-queues/test_queue", "GET"),
]


# Build parametrized test IDs
def _build_endpoint_params():
    """Generate parametrized test cases from endpoint definitions."""
    params = []

    for endpoint, method in ADMIN_ONLY_ENDPOINTS:
        params.append(
            pytest.param(
                endpoint,
                method,
                [ServerRoles.ADMIN],
                id=f"admin_only_{method}_{endpoint.replace('/', '_')}",
            )
        )

    for endpoint, method in ADMIN_MANAGER_ENDPOINTS:
        params.append(
            pytest.param(
                endpoint,
                method,
                [ServerRoles.ADMIN, ServerRoles.MANAGER],
                id=f"admin_mgr_{method}_{endpoint.replace('/', '_')}",
            )
        )

    for endpoint, method in ADMIN_MANAGER_CONTRIBUTOR_ENDPOINTS:
        params.append(
            pytest.param(
                endpoint,
                method,
                [
                    ServerRoles.ADMIN,
                    ServerRoles.MANAGER,
                    ServerRoles.CONTRIBUTOR,
                ],
                id=f"admin_mgr_contrib_{method}_{endpoint.replace('/', '_')}",
            )
        )

    return params


class TestAuthzPrivilegeEscalation:
    """Test authorization failures and privilege escalation attempts."""

    @pytest.mark.parametrize(
        "endpoint,method,required_roles", _build_endpoint_params()
    )
    def test_authz_fail_unauthenticated(
        self, endpoint, method, required_roles, mongo_app, caplog
    ):
        """
        Verify authz_fail is logged when unauthenticated user
        attempts to access protected endpoint.
        """
        app, _ = mongo_app

        with caplog.at_level(logging.CRITICAL):
            if method == "GET":
                response = app.get(endpoint)
            elif method == "POST":
                response = app.post(endpoint, json={})
            elif method == "PUT":
                response = app.put(endpoint, json={})
            elif method == "DELETE":
                response = app.delete(endpoint)

        assert response.status_code == HTTPStatus.UNAUTHORIZED
        assert "authz_fail:unauthenticated" in caplog.text

    @pytest.mark.parametrize(
        "endpoint,method,required_roles", _build_endpoint_params()
    )
    def test_authz_fail_insufficient_role(
        self, endpoint, method, required_roles, mongo_app, caplog
    ):
        """
        Verify authz_fail is logged when authenticated user with
        insufficient role attempts to access protected endpoint.
        """
        # Setup: Create CONTRIBUTOR token (lowest privileged user role)
        import os

        os.environ["JWT_SIGNING_KEY"] = "my_secret_key"
        app, mongo = mongo_app

        # Insert CONTRIBUTOR client
        contributor_id = "test_contributor"
        contributor_key = "test_key"
        client_salt = bcrypt.gensalt()
        client_key_hash = bcrypt.hashpw(
            contributor_key.encode("utf-8"), client_salt
        ).decode("utf-8")

        mongo.client_permissions.insert_one(
            {
                "client_id": contributor_id,
                "client_secret_hash": client_key_hash,
                "role": ServerRoles.CONTRIBUTOR,
                "max_priority": {},
                "allowed_queues": [],
                "max_reservation_time": {},
            }
        )

        # Get token for CONTRIBUTOR
        token = get_access_token(app, contributor_id, contributor_key)

        # Skip test if endpoint doesn't require higher privileges
        # (CONTRIBUTOR satisfies ADMIN_MANAGER_CONTRIBUTOR)
        if required_roles == [
            ServerRoles.ADMIN,
            ServerRoles.MANAGER,
            ServerRoles.CONTRIBUTOR,
        ]:
            pytest.skip(
                f"CONTRIBUTOR has access to {endpoint} "
                "(endpoint requires CONTRIBUTOR)"
            )

        with caplog.at_level(logging.CRITICAL):
            if method == "GET":
                response = app.get(endpoint, headers={"Authorization": token})
            elif method == "POST":
                response = app.post(
                    endpoint, json={}, headers={"Authorization": token}
                )
            elif method == "PUT":
                response = app.put(
                    endpoint, json={}, headers={"Authorization": token}
                )
            elif method == "DELETE":
                response = app.delete(
                    endpoint, headers={"Authorization": token}
                )

        if response.status_code != HTTPStatus.FORBIDDEN:
            print(f"Response: {response.data}")
        assert response.status_code == HTTPStatus.FORBIDDEN, (
            f"Expected 403, got {response.status_code}: {response.data}"
        )
        assert f"authz_fail:{contributor_id}" in caplog.text

        # Cleanup
        mongo.client_permissions.delete_one({"client_id": contributor_id})


class TestAuthenticationEvents:
    """Test authentication-related logging events."""

    def test_authn_login_success(self, mongo_app_with_permissions, caplog):
        """Verify authn_login_success is logged on successful token
        creation.
        """
        app, _, client_id, client_key, _ = mongo_app_with_permissions

        with caplog.at_level(logging.INFO):
            response = app.post(
                "/v1/oauth2/token",
                headers=create_auth_header(client_id, client_key),
            )

        assert response.status_code == HTTPStatus.OK
        assert f"authn_login_success:{client_id}" in caplog.text

    def test_authn_login_fail_invalid_credentials(
        self, mongo_app_with_permissions, caplog
    ):
        """Verify authn_login_fail is logged on invalid credentials."""
        app, _, _, _, _ = mongo_app_with_permissions

        with caplog.at_level(logging.WARNING):
            response = app.post(
                "/v1/oauth2/token",
                headers=create_auth_header("wrong_id", "wrong_key"),
            )

        assert response.status_code == HTTPStatus.UNAUTHORIZED
        assert "authn_login_fail:wrong_id" in caplog.text

    def test_authn_token_created(self, mongo_app_with_permissions, caplog):
        """Verify authn_token_created is logged when access token is issued."""
        app, _, client_id, client_key, _ = mongo_app_with_permissions

        with caplog.at_level(logging.INFO):
            response = app.post(
                "/v1/oauth2/token",
                headers=create_auth_header(client_id, client_key),
            )

        assert response.status_code == HTTPStatus.OK
        # Token created event includes userid and entitlements
        assert f"authn_token_created:{client_id}" in caplog.text

    def test_authn_token_revoked(self, mongo_app_with_permissions, caplog):
        """Verify authn_token_revoked is logged when refresh token
        is revoked.
        """
        import os

        os.environ["JWT_SIGNING_KEY"] = "my_secret_key"
        app, mongo, client_id, client_key, _ = mongo_app_with_permissions
        admin_token = get_access_token(app, client_id, client_key)

        # Create a secondary client and get its refresh token
        test_client_id = "test_revoke_client"
        test_client_key = "test_key"
        client_salt = bcrypt.gensalt()
        client_key_hash = bcrypt.hashpw(
            test_client_key.encode("utf-8"), client_salt
        ).decode("utf-8")

        mongo.client_permissions.insert_one(
            {
                "client_id": test_client_id,
                "client_secret_hash": client_key_hash,
                "role": ServerRoles.CONTRIBUTOR,
                "max_priority": {},
                "allowed_queues": [],
                "max_reservation_time": {},
            }
        )

        # Get token for secondary client
        token_response = app.post(
            "/v1/oauth2/token",
            headers=create_auth_header(test_client_id, test_client_key),
        )
        refresh_token = token_response.get_json()["refresh_token"]

        # Revoke the refresh token
        with caplog.at_level(logging.INFO):
            response = app.post(
                "/v1/oauth2/revoke",
                json={"refresh_token": refresh_token},
                headers={"Authorization": admin_token},
            )

        assert response.status_code == HTTPStatus.OK
        # Verify token revocation is logged
        assert f"authn_token_revoked:{test_client_id}" in caplog.text

        # Cleanup
        mongo.client_permissions.delete_one({"client_id": test_client_id})
        mongo.refresh_tokens.delete_many({"client_id": test_client_id})
