# Copyright (C) 2024 Canonical
#
# Test authorization and role-based access control for v1 API endpoints.

from http import HTTPStatus
from pathlib import Path
from typing import Dict

import json
import os
import pytest

from testflinger_common.enums import ServerRoles


ALL_ROLES = set("AGENT", "CONTRIBUTOR", "MANAGER", "ADMIN")


def build_param_from_perms():
    """Read in the JSON file with the ruleset for urls allowed for roles."""
    perms_path = Path(__file__).parent / "permissions.json"
    with open(perms_path) as f:
        perms = json.load(f)

    # Generate parametrize data dynamically!
    params = []
    for endpoint, methods in perms.items():
        for method, roles in methods.items():
            case_id = f"{method}:{endpoint.replace('/', '_')}:{'AND_'.join(roles)}" # noqa E501
            params.append(pytest.param({}, id=case_id))

    return pytest.mark.parametrize("auth_scenario", params)


@pytest.fixture
def endpoint_permissions():
    """Endpoint permissions fixture, reads from permissions.json."""
    perms_path = Path(__file__).parent / "permissions.json"
    yield json.loads(perms_path.read_text())


# TODO: test the following
#   "/v1/oauth2/refresh": {
#     "POST": ["AGENT", "CONTRIBUTOR", "MANAGER", "ADMIN"]
#   },
#   "/v1/oauth2/revoke": {
#     "POST": ["ADMIN"]
#   },
#   "/v1/oauth2/token": {
#     "POST": ["AGENT", "CONTRIBUTOR", "MANAGER", "ADMIN"]
#   },


def do_call(app, method, endpoint, headers):
    if method.lower() == "get":
        response = app.get(endpoint, headers=headers)
    elif method.lower() == "post":
        response = app.post(endpoint, headers=headers, json={})
    elif method.lower() == "put":
        response = app.put(endpoint, headers=headers, json={})
    elif method.lower() == "delete":
        response = app.delete(endpoint, headers=headers, json={})
    else:
        raise ValueError(
            "do_call expected one of GET, PUT, POST, DELETE, not {}", method
            )
    return response


@build_param_from_perms()
class TestAllEndPoints:
    """Test authorization for each url."""

    @pytest.mark.parametrize("auth_type", ["bearer_header", None])
    def test_permissions_with_oidc_enabled(
        self, auth_scenario, oidc_app, auth_type, role_clients_factory
    ):
        """
        For each url, show that the proper roles work and the wrong roles are
        not allowed access.

        When OIDC is enabled, as will be the case in this test, an "access"
        token is required to conenct to ANY endpoint (other than those needed
        to acquire the access token in the first place). This test will show
        that each authorized role will be able to access each given endpoint
        while any role outside of that will be denied (403 Forbidden).

        Anonymous (no auth) is strictly disallowed (401 Unauthorized).
        """
        app, _ = oidc_app
        endpoint = auth_scenario["endpoint"]
        method = auth_scenario["method"]
        allowed_roles = auth_scenario["required_role"]
        forbidden_roles = ALL_ROLES.difference(allowed_roles)

        if auth_type:
            # When OIDC is enabled and an access token is provided, verify
            # the expected roles are able to access this endpoint.

            # Verify that roles which are not permitted recieve 403 Forbidden
            for role in [ServerRoles(r) for r in forbidden_roles]:
                data = role_clients_factory[role]
                headers = data[auth_type]
                response = do_call(app, method, endpoint, headers)
                assert response.status_code == HTTPStatus.FORBIDDEN

            # Verify that roles which ARE permitted to access this endpoint are
            # allowed to use the endpoint normally.
            for role in [ServerRoles(r) for r in forbidden_roles]:
                data = role_clients_factory[role]
                headers = data[auth_type]
                response = do_call(app, method, endpoint, headers)
                assert response.status_code in (HTTPStatus.OK)
        else:
            response = do_call(app, method, endpoint, headers=None)
            assert response.status_code in (HTTPStatus.UNAUTHORIZED)


    @pytest.mark.parametrize("auth_type", ["bearer_header", None])
    def test_permissions_without_oidc_enabled(
        self, auth_scenario, oidc_app, auth_type, role_clients_factory
    ):
        """
        For each url, show that the proper roles work and the wrong roles are
        not allowed access.

        When OIDC is disabled, as will be the case in this test, an access
        token is required to connect to some endpoints but not for all
        endpoints, as anonymous access is allowed with a default role of
        CONTRIBUTOR. This test will show that each role will be able to
        access the endpoints which require a role other than CONTRIBUTOR.

        Anonymous (no auth) is treated as CONTRIBUTOR.
        """
        app, _ = oidc_app
        endpoint = auth_scenario["endpoint"]
        method = auth_scenario["method"]
        allowed_roles = auth_scenario["required_role"]
        forbidden_roles = ALL_ROLES.difference(allowed_roles)

        if auth_type:
            # When OIDC is disabled and an access token is provided, verify
            # the expected roles are able to access this endpoint.

            # Verify that roles which are not permitted recieve 403 Forbidden
            for role in [ServerRoles(r) for r in forbidden_roles]:
                data = role_clients_factory[role]
                headers = data[auth_type]
                response = do_call(app, method, endpoint, headers)
                assert response.status_code == HTTPStatus.FORBIDDEN

            # Verify that roles which ARE permitted to access this endpoint are
            # allowed to use the endpoint normally.
            for role in [ServerRoles(r) for r in forbidden_roles]:
                data = role_clients_factory[role]
                headers = data[auth_type]
                response = do_call(app, method, endpoint, headers)
                assert response.status_code in (HTTPStatus.OK)
        else:
            # Verify anonymous access is treated as CONTRIBUTOR:
            headers = None
            if ServerRoles.CONTRIBUTOR in forbidden_roles:
                response = do_call(app, method, endpoint, headers)
                assert response.status_code in (HTTPStatus.FORBIDDEN)
            else: # allowed
                response = do_call(app, method, endpoint, headers)
                assert response.status_code in (HTTPStatus.OK)
