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
import os
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


# All available roles from enum, sorted by enum order
ALL_ROLES = sorted(ServerRoles)

# Define endpoints by required role
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

# Map endpoints to allowed roles
ENDPOINT_ALLOWED_ROLES = {}
for endpoint, method in ADMIN_ONLY_ENDPOINTS:
    key = (endpoint, method)
    ENDPOINT_ALLOWED_ROLES[key] = [ServerRoles.ADMIN]

for endpoint, method in ADMIN_MANAGER_ENDPOINTS:
    key = (endpoint, method)
    ENDPOINT_ALLOWED_ROLES[key] = [ServerRoles.ADMIN, ServerRoles.MANAGER]

for endpoint, method in ADMIN_MANAGER_CONTRIBUTOR_ENDPOINTS:
    key = (endpoint, method)
    ENDPOINT_ALLOWED_ROLES[key] = [
        ServerRoles.ADMIN,
        ServerRoles.MANAGER,
        ServerRoles.CONTRIBUTOR,
    ]


def _build_endpoint_params():
    """Generate parametrized test cases testing all non-allowed roles."""
    params = []

    for (endpoint, method), allowed_roles in ENDPOINT_ALLOWED_ROLES.items():
        # Test with all roles that are NOT allowed
        denied_roles = [r for r in ALL_ROLES if r not in allowed_roles]

        for denied_role in denied_roles:
            test_id = (
                f"{method}_{endpoint.replace('/', '_')}_{denied_role.value}"
            )
            params.append(
                pytest.param(
                    endpoint,
                    method,
                    denied_role,
                    id=test_id,
                )
            )

    return params


class TestAuthzPrivilegeEscalation:
    """Test authorization failures and privilege escalation attempts."""

    def test_authz_fail_unauthenticated(self, mongo_app, caplog):
        """
        Verify authz_fail is logged when unauthenticated user
        attempts to access protected endpoint.
        """
        app, _ = mongo_app

        # Test one endpoint as representative case
        endpoint = ADMIN_ONLY_ENDPOINTS[0][0]
        method = ADMIN_ONLY_ENDPOINTS[0][1]

        with caplog.at_level(logging.INFO):
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
        "endpoint,method,test_role", _build_endpoint_params()
    )
    def test_authz_fail_insufficient_role(
        self, endpoint, method, test_role, mongo_app, caplog
    ):
        """
        Verify authz_fail is logged when authenticated user with
        insufficient role attempts to access protected endpoint.
        """
        os.environ["JWT_SIGNING_KEY"] = "my_secret_key"
        app, mongo = mongo_app

        # Create client with test role
        client_id = f"test_client_{test_role.value}"
        client_key = "test_key"
        client_salt = bcrypt.gensalt()
        client_key_hash = bcrypt.hashpw(
            client_key.encode("utf-8"), client_salt
        ).decode("utf-8")

        mongo.client_permissions.insert_one(
            {
                "client_id": client_id,
                "client_secret_hash": client_key_hash,
                "role": test_role,
                "max_priority": {},
                "allowed_queues": [],
                "max_reservation_time": {},
            }
        )

        # Get token for test role
        token = get_access_token(app, client_id, client_key)

        with caplog.at_level(logging.INFO):
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

        assert response.status_code == HTTPStatus.FORBIDDEN, (
            f"Expected 403 for {test_role.value} on {method} {endpoint}, "
            f"got {response.status_code}: {response.data}"
        )
        assert f"authz_fail:{client_id}" in caplog.text

        # Cleanup
        mongo.client_permissions.delete_one({"client_id": client_id})


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


class TestLoggingCompleteness:
    """Comprehensive tests for all OWASP logging event scenarios."""

    def test_oidc_success_login(self, oidc_app, caplog):
        """Verify authn_login_success is logged for successful OIDC
        callback.
        """
        from unittest.mock import Mock, patch

        from authlib.common.security import generate_token
        from flask import url_for

        app, mongo = oidc_app

        # Mock OIDC token response
        mock_token = {
            "access_token": generate_token(48),
            "userinfo": {
                "sub": "1234",
                "name": "testuser",
                "email": "test@example.com",
            },
        }

        with patch(
            "testflinger.oidc.views.current_app", new_callable=Mock
        ) as mock_current_app:
            # Setup the mock to match real Flask app behavior
            mock_current_app.oauth.oidc.authorize_access_token.return_value = (
                mock_token
            )
            mock_current_app.owasp_logger = app.owasp_logger

            client = app.test_client()
            with caplog.at_level(logging.INFO):
                with app.test_request_context():
                    response = client.get(url_for("oidc.callback"))

            assert response.status_code == HTTPStatus.FOUND
            assert "authn_login_success:testuser" in caplog.text

    def test_oidc_failed_login(self, oidc_app, caplog):
        """Verify authn_login_fail is logged for failed OIDC callback."""
        from unittest.mock import Mock, patch

        from authlib.integrations.base_client.errors import OAuthError
        from flask import url_for

        app, _ = oidc_app

        with patch(
            "testflinger.oidc.views.current_app", new_callable=Mock
        ) as mock_current_app:
            mock_current_app.oauth.oidc.authorize_access_token.side_effect = (
                OAuthError("Invalid OAuth response")
            )
            mock_current_app.owasp_logger = app.owasp_logger

            client = app.test_client()
            with caplog.at_level(logging.INFO):
                with app.test_request_context():
                    response = client.get(url_for("oidc.callback"))

            assert response.status_code == HTTPStatus.FOUND
            assert "authn_login_fail:unknown" in caplog.text
            assert "OAuthError" in caplog.text

    def test_token_refresh_success(self, mongo_app_with_permissions, caplog):
        """Verify authn_token_created logged for successful token refresh."""
        import os

        os.environ["JWT_SIGNING_KEY"] = "my_secret_key"
        app, mongo, client_id, client_key, _ = mongo_app_with_permissions

        # Get initial token
        token_response = app.post(
            "/v1/oauth2/token",
            headers=create_auth_header(client_id, client_key),
        )
        refresh_token = token_response.get_json()["refresh_token"]

        # Refresh the token
        with caplog.at_level(logging.INFO):
            response = app.post(
                "/v1/oauth2/refresh",
                json={"refresh_token": refresh_token},
            )

        assert response.status_code == HTTPStatus.OK
        assert f"authn_token_created:{client_id}" in caplog.text
        assert "Access token refreshed" in caplog.text

    def test_token_reuse_expired(self, mongo_app_with_permissions, caplog):
        """Verify authn_token_reuse is logged for expired token reuse."""
        import os
        from datetime import datetime, timedelta, timezone

        from testflinger import database

        os.environ["JWT_SIGNING_KEY"] = "my_secret_key"
        app, mongo, client_id, client_key, _ = mongo_app_with_permissions

        # Get initial token
        token_response = app.post(
            "/v1/oauth2/token",
            headers=create_auth_header(client_id, client_key),
        )
        refresh_token = token_response.get_json()["refresh_token"]

        # Manually expire the token by modifying the database
        expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        database.edit_refresh_token(refresh_token, {"expires_at": expires_at})

        # Attempt to refresh with expired token
        with caplog.at_level(logging.INFO):
            response = app.post(
                "/v1/oauth2/refresh",
                json={"refresh_token": refresh_token},
            )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert f"authn_token_reuse:{client_id}" in caplog.text
        assert "expired" in caplog.text

    def test_token_reuse_revoked(self, mongo_app_with_permissions, caplog):
        """Verify authn_token_reuse is logged for revoked token reuse."""
        import os

        from testflinger import database

        os.environ["JWT_SIGNING_KEY"] = "my_secret_key"
        app, mongo, client_id, client_key, _ = mongo_app_with_permissions

        # Get initial token
        token_response = app.post(
            "/v1/oauth2/token",
            headers=create_auth_header(client_id, client_key),
        )
        refresh_token = token_response.get_json()["refresh_token"]

        # Revoke the token
        database.edit_refresh_token(refresh_token, {"revoked": True})

        # Attempt to refresh with revoked token
        with caplog.at_level(logging.INFO):
            response = app.post(
                "/v1/oauth2/refresh",
                json={"refresh_token": refresh_token},
            )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert f"authn_token_reuse:{client_id}" in caplog.text
        assert "revoked" in caplog.text

    def test_user_created(self, mongo_app_with_permissions, caplog):
        """Verify user_created event logged when new client created."""
        import os

        os.environ["JWT_SIGNING_KEY"] = "my_secret_key"
        app, mongo, admin_client_id, admin_key, _ = mongo_app_with_permissions

        admin_token = get_access_token(app, admin_client_id, admin_key)
        new_client_id = "new_test_client_created"

        with caplog.at_level(logging.INFO):
            response = app.put(
                f"/v1/client-permissions/{new_client_id}",
                json={
                    "client_secret": "new_secret",
                    "role": ServerRoles.CONTRIBUTOR,
                },
                headers={"Authorization": admin_token},
            )

        assert response.status_code == HTTPStatus.OK
        # Verify log event contains userid, target_user, and entitlements
        assert f"user_created:{admin_client_id}" in caplog.text
        assert new_client_id in caplog.text
        assert "CONTRIBUTOR" in caplog.text or "created" in caplog.text

        # Cleanup
        mongo.client_permissions.delete_one({"client_id": new_client_id})

    def test_user_created_new_client(self, mongo_app_with_permissions, caplog):
        """Verify user_created is logged when a new client is created."""
        import os

        os.environ["JWT_SIGNING_KEY"] = "my_secret_key"
        app, mongo, admin_client_id, admin_key, _ = mongo_app_with_permissions

        admin_token = get_access_token(app, admin_client_id, admin_key)
        new_client_id = "new_test_client"

        with caplog.at_level(logging.INFO):
            response = app.put(
                f"/v1/client-permissions/{new_client_id}",
                json={
                    "client_secret": "new_secret",
                    "role": ServerRoles.CONTRIBUTOR,
                },
                headers={"Authorization": admin_token},
            )

        assert response.status_code == HTTPStatus.OK
        assert f"user_created:{admin_client_id}" in caplog.text
        assert new_client_id in caplog.text
        assert "created" in caplog.text

        # Cleanup
        mongo.client_permissions.delete_one({"client_id": new_client_id})

    def test_user_updated(self, mongo_app_with_permissions, caplog):
        """Verify user_updated event logged when client role changed."""
        import os

        os.environ["JWT_SIGNING_KEY"] = "my_secret_key"
        app, mongo, admin_client_id, admin_key, _ = mongo_app_with_permissions

        admin_token = get_access_token(app, admin_client_id, admin_key)
        target_client_id = "update_test_client_explicit"

        # Create client with CONTRIBUTOR role
        app.put(
            f"/v1/client-permissions/{target_client_id}",
            json={
                "client_secret": "new_secret",
                "role": ServerRoles.CONTRIBUTOR,
            },
            headers={"Authorization": admin_token},
        )

        # Update to MANAGER role and capture logging
        with caplog.at_level(logging.INFO):
            response = app.put(
                f"/v1/client-permissions/{target_client_id}",
                json={"role": ServerRoles.MANAGER},
                headers={"Authorization": admin_token},
            )

        assert response.status_code == HTTPStatus.OK
        # Verify log event contains userid, target_user, and new role
        assert f"user_updated:{admin_client_id}" in caplog.text
        assert target_client_id in caplog.text
        assert "MANAGER" in caplog.text or "updated" in caplog.text

        # Cleanup
        mongo.client_permissions.delete_one({"client_id": target_client_id})

    def test_user_updated_existing_client(
        self, mongo_app_with_permissions, caplog
    ):
        """Verify user_updated is logged when an existing client is updated."""
        import os

        os.environ["JWT_SIGNING_KEY"] = "my_secret_key"
        app, mongo, admin_client_id, admin_key, _ = mongo_app_with_permissions

        admin_token = get_access_token(app, admin_client_id, admin_key)

        # Create a new client first
        new_client_id = "update_test_client"
        app.put(
            f"/v1/client-permissions/{new_client_id}",
            json={
                "client_secret": "new_secret",
                "role": ServerRoles.CONTRIBUTOR,
            },
            headers={"Authorization": admin_token},
        )

        # Now update the client
        caplog.clear()
        with caplog.at_level(logging.INFO):
            response = app.put(
                f"/v1/client-permissions/{new_client_id}",
                json={"role": ServerRoles.MANAGER},
                headers={"Authorization": admin_token},
            )

        assert response.status_code == HTTPStatus.OK
        assert f"user_updated:{admin_client_id}" in caplog.text
        assert new_client_id in caplog.text
        assert "updated" in caplog.text

        # Cleanup
        mongo.client_permissions.delete_one({"client_id": new_client_id})

    def test_user_deleted_client(self, mongo_app_with_permissions, caplog):
        """Verify user_deleted is logged when a client is deleted."""
        import os

        os.environ["JWT_SIGNING_KEY"] = "my_secret_key"
        app, mongo, admin_client_id, admin_key, _ = mongo_app_with_permissions

        admin_token = get_access_token(app, admin_client_id, admin_key)

        # Create a new client first
        delete_test_client = "delete_test_client"
        app.put(
            f"/v1/client-permissions/{delete_test_client}",
            json={
                "client_secret": "new_secret",
                "role": ServerRoles.CONTRIBUTOR,
            },
            headers={"Authorization": admin_token},
        )

        # Now delete the client
        with caplog.at_level(logging.INFO):
            response = app.delete(
                f"/v1/client-permissions/{delete_test_client}",
                headers={"Authorization": admin_token},
            )

        assert response.status_code == HTTPStatus.OK
        assert f"user_deleted:{admin_client_id}" in caplog.text
        assert delete_test_client in caplog.text
        assert "deleted" in caplog.text
