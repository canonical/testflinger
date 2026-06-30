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
Unit tests for permissions on every endpoint and method in the
Testflinger API.
"""

import json
from http import HTTPStatus
from io import BytesIO
from pathlib import Path

import pytest
from testflinger_common.enums import ServerRoles

from tests.utilities import get_access_token_header, get_refresh_token

ALL_ROLES = {
    ServerRoles(r) for r in ("AGENT", "CONTRIBUTOR", "MANAGER", "ADMIN")
}


def build_param_from_perms():
    """Read in the JSON file with the ruleset for urls allowed for roles."""
    perms_path = Path(__file__).parent / "permissions.json"
    with open(perms_path) as f:
        perms = json.load(f)

    # Generate parametrize data dynamically!
    params = []
    for endpoint, methods in perms.items():
        for method, roles in methods.items():
            case_id = (
                f"{method}:{endpoint.replace('/', '_')}:"
                f"{'+'.join((str(x) for x in roles))}"
            )
            params.append(
                pytest.param(
                    {
                        "endpoint": endpoint,
                        "method": method,
                        "required_role": [
                            (ServerRoles(r) if r else None) for r in roles
                        ],
                    },
                    id=case_id,
                )
            )

    return pytest.mark.parametrize("auth_scenario", params)


@pytest.fixture
def endpoint_permissions():
    """Endpoint permissions fixture, reads from permissions.json."""
    perms_path = Path(__file__).parent / "permissions.json"
    yield json.loads(perms_path.read_text())


def headers_for(role_data, endpoint, auth_type):
    """
    Select the auth header to use for a role client on a given endpoint.

    `role_data` is the per-role client dict from `role_clients_factory` (or
    None for anonymous access). The token endpoint authenticates via HTTP
    Basic (client credentials) rather than a bearer token, so it uses the
    basic header; everything else uses the requested `auth_type` header.
    """
    if role_data is None:
        return None
    if "oauth2/token" in endpoint:
        return role_data["basic_header"]
    return role_data[auth_type]


def do_call(app, method, endpoint, role_data, webhook_fixture, auth_type):
    """
    Do whatever special thing needs to be done with the given endpoint,
    which may contain angle-bracket notation like /v1/job/<job_id> and
    such that the calls all WILL succeed when the properly privileged
    role is used to make the call.

    `role_data` is the per-role client dict from `role_clients_factory` (or
    None for anonymous access); the role, client id and auth headers are all
    derived from it.

    Depending on the endpoint, this might require adding dependent data
    elements (e.g. a job before results) as needed. Set up actions will
    use any appropriate role to make the setup successful, where as the
    main call will use the role's headers.
    """
    headers = headers_for(role_data, endpoint, auth_type)
    # Note: endpoint will have angle-bracketed variables replaced and the
    #       updated endpoint returned (e.g. <job_id>)
    endpoint, data = do_setup(
        app, method, endpoint, role_data, webhook_fixture, auth_type
    )

    if method.lower() == "get":
        response = app.get(endpoint, headers=headers)
    elif method.lower() == "post":
        if "artifact" in endpoint:
            # File-upload endpoints must be sent as multipart/form-data, not
            # JSON, because the payload contains a BytesIO stream that is not
            # JSON serializable (mirrors test_results.py::test_artifact_post).
            response = app.post(
                endpoint,
                headers=headers,
                data=data,
                content_type="multipart/form-data",
            )
        else:
            response = app.post(endpoint, headers=headers, json=data)
    elif method.lower() == "put":
        response = app.put(endpoint, headers=headers, json=data)
    elif method.lower() == "delete":
        if "restricted-queue" in endpoint:
            response = app.delete(endpoint, headers=headers, json=data)
        else:
            response = app.delete(endpoint, headers=headers)
    else:
        raise ValueError(
            "do_call expected one of GET, PUT, POST, DELETE, not {}", method
        )
    return response


def do_setup(
    app, method, endpoint, role_data, webhook_fixture, auth_type
) -> tuple:
    """
    Do whatever special thing needs to be done with the given endpoint,
    which may contain angle-bracket notation like /v1/job/<job_id> and
    such that the calls all WILL succeed when the properly privileged
    role is used to make the call.

    `role_data` is the per-role client dict from `role_clients_factory` (or
    None for anonymous access); the role, client id and auth headers are all
    derived from it.

    Depending on the endpoint, this might require adding dependent data
    elements (e.g. a job before results) as needed. Set up actions will
    use any appropriate role to make the setup successful, where as the
    main call will use the role's headers.
    """
    headers = headers_for(role_data, endpoint, auth_type)
    client_id = role_data["id"] if role_data else None
    role = role_data["role"] if role_data else ServerRoles.CONTRIBUTOR
    test_data = None
    # Each endpoint + method may require special set-up in order to test a
    # command that is EXPECTED TO SUCCEED except for the permissions.
    # We will make every attempt to find the shortest, smallest logic that
    # can implement the appropriate setup for the upcoming test command.
    # Note: we rely on the app and database being implemented as fixtures
    # and make no attempt to clean up as a result.

    setup_client = "setup"
    setup_role = ServerRoles.ADMIN
    setup_headers = get_access_token_header(setup_client, setup_role)

    agent_data = {"state": "waiting", "queues": ["qqqq"], "location": "here"}
    job_data = {"job_queue": "qqqq"}
    if "/attachments" in endpoint:
        job_data.update({"test_data": {"attachments": [{"agent": "filenam"}]}})
    need_agent = False
    need_job = False
    need_client = False
    is_agent = role and (ServerRoles(role) == ServerRoles.AGENT)

    if "/restricted-queue" in endpoint:
        need_client = True
        need_agent = True
    if "oauth2/r" in endpoint:
        need_client = True

    if endpoint == "/v1/job":
        if method in ("GET", "DELETE"):
            need_agent = True
            endpoint += "?queue=qqqq"
        else:
            test_data = job_data

    # Note: This also includes "/jobs" at any place in the uri.
    if "/job" in endpoint and method in ("GET", "DELETE"):
        need_job = True

    if "<queue_name>" in endpoint or need_agent:
        need_agent = True
        queue_name = "qqqq"
        endpoint = endpoint.replace("<queue_name>", queue_name)

    if "<agent_name>" in endpoint or need_agent:
        agent_name = "agent-one"
        # the agent that we will test needs to be registered first
        response = app.post(
            f"/v1/agents/data/{agent_name}",
            json=agent_data,
            headers=headers if is_agent else setup_headers,
        )
        assert response.status_code == HTTPStatus.OK, (
            f"{response.status} {response.data}"
        )
        endpoint = endpoint.replace("<agent_name>", agent_name)

    if "<job_id>" in endpoint or need_job:
        response = app.post("/v1/job", json=job_data, headers=setup_headers)
        job_id = response.json.get("job_id")
        assert response.status_code == HTTPStatus.OK, (
            f"{response.status} {response.data}"
        )
        endpoint = endpoint.replace("<job_id>", job_id)

    if "<log_type>" in endpoint:
        log_type = "output"
        test_data = {
            "fragment_number": 0,
            "timestamp": "2014-12-22T03:12:58.019077+00:00",
            "phase": "test",
            "log_data": "some log output",
        }
        endpoint = endpoint.replace("<log_type>", log_type)

    if "<path>" in endpoint:
        path = "path"
        # This section is explicitly for setting up secrets.
        # The secrets endpoints require an authenticated client identity
        # (client_id in the URL must match the authenticated client). They do
        # NOT consult the client_permissions table, so no registration is
        # needed; the authenticated client's own id is used as <client_id>.
        cid = client_id if client_id is not None else "anon"
        endpoint = endpoint.replace("<client_id>", cid)
        endpoint = endpoint.replace("<path>", path)
        # The PUT main call requires a secret value in the body.
        test_data = {"value": "don't tell anyone!"}
        if method in ("GET", "DELETE"):
            # Best-effort pre-create: only an authorized client can write a
            # secret (and only into its own namespace). Forbidden roles will
            # be rejected here AND on the main call, so we don't assert.
            app.put(
                endpoint,
                json={"value": "don't tell anyone!"},
                headers=headers,
            )
    elif "<client_id>" in endpoint or need_client:
        client_id = "client_id"
        response = app.put(
            f"/v1/client-permissions/{client_id}",
            json={
                "client_secret": "always_needed",
                "role": ServerRoles.CONTRIBUTOR,
            },
            headers=setup_headers,
        )
        assert response.status_code == HTTPStatus.OK, (
            f"{response.status} {response.data}"
        )
        endpoint = endpoint.replace("<client_id>", client_id)

    # client_id must already exist
    if "oauth2/revoke" in endpoint:
        test_data = {
            "refresh_token": get_refresh_token(app, client_id, "always_needed")
        }

    if "/restricted-queue" in endpoint:
        assert client_id is not None
        test_data = {"client_id": client_id}
        if method in ("GET", "DELETE"):
            response = app.post(
                f"/v1/restricted-queues/{queue_name}",
                json=test_data,
                headers=setup_headers,
            )
            assert response.status_code == HTTPStatus.OK, (
                f"{response.status} {response.data}"
            )

    if "images" in endpoint:
        test_data = {
            "qqqq": {
                "image1": "url: http://path/to/image1",
                "image2": "url: http://path/to/image2",
            }
        }
        if method in ("GET", "DELETE"):
            response = app.post(
                "/v1/agents/images", json=test_data, headers=setup_headers
            )
            assert response.status_code == HTTPStatus.OK, (
                f"{response.status} {response.data}"
            )

    if "provision_logs" in endpoint:
        test_data = {
            "job_id": "00000000-0000-0000-0000-00000000000",
            "exit_code": 1,
            "detail": "provision_failed",
        }

    if "/action" in endpoint:
        test_data = {"action": "cancel"}

    if "/events" in endpoint:
        test_data = {
            "agent_id": "agent1",
            "job_queue": "myjobqueue",
            "job_status_webhook": webhook_fixture,
            "events": [
                {
                    "event_name": "my_event",
                    "timestamp": "2014-12-22T03:12:58.019077+00:00",
                    "detail": "mymsg",
                }
            ],
        }

    if "/v1/agents/queues" in endpoint:
        test_data = {"qfoo": "this is a test queue"}
        if method in ("GET", "DELETE"):
            app.post(
                "/v1/agents/queues",
                json=test_data,
                headers=headers if is_agent else setup_headers,
            )

    if "/attachments" in endpoint:
        # the "attachment" that we are using is this `__file__` which exists
        # submit the attachments archive for the job
        filename = __file__
        with open(filename, "rb") as attachments:
            response = app.post(
                f"/v1/job/{job_id}/attachments",
                data={"file": (attachments, filename)},
                content_type="multipart/form-data",
                headers=setup_headers,
            )
            assert response.status_code == HTTPStatus.OK, (
                f"{response.status} {response.data}"
            )

    if "artifact" in endpoint:
        data = b"test file content"
        test_data = {"file": (BytesIO(data), "artifact.tgz")}
        # special case: must be an agent
        setup_role = ServerRoles.AGENT
        setup_headers = get_access_token_header(setup_client, setup_role)
        if method in ("GET", "DELETE"):
            response = app.post(
                endpoint,
                data=test_data,
                content_type="multipart/form-data",
                headers=headers if is_agent else setup_headers,
            )
            assert response.status_code == HTTPStatus.OK, (
                f"{response.status} {response.data}"
            )

    return endpoint, test_data


@build_param_from_perms()
class TestAllEndPoints:
    """Test authorization for each url."""

    @pytest.mark.parametrize("auth_type", ["bearer_header", None])
    def test_permissions_with_oidc_enabled(
        self,
        auth_scenario,
        oidc_app,
        auth_type,
        role_clients_factory,
        webhook_fixture,
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
        app = oidc_app[0].test_client()
        endpoint = auth_scenario["endpoint"]
        method = auth_scenario["method"]
        allowed_roles = auth_scenario["required_role"]
        forbidden_roles = ALL_ROLES.difference(allowed_roles)

        if auth_type:
            # When OIDC is enabled and an access token is provided, verify
            # the expected roles are able to access this endpoint.

            # Verify that roles which are not permitted recieve 403 Forbidden
            for role in forbidden_roles:
                response = do_call(
                    app,
                    method,
                    endpoint,
                    role_clients_factory[role],
                    webhook_fixture,
                    auth_type,
                )
                assert response.status_code == HTTPStatus.FORBIDDEN, (
                    f"Role {role}, Method {method}, URI {endpoint}: was "
                    f"expected to be forbidden (403) not {response.status} "
                    f"{response.data}"
                )

            # Verify that roles which ARE permitted to access this endpoint are
            # allowed to use the endpoint normally.
            for role in allowed_roles:
                response = do_call(
                    app,
                    method,
                    endpoint,
                    role_clients_factory[role],
                    webhook_fixture,
                    auth_type,
                )
                assert response.status_code == HTTPStatus.OK, (
                    f"Role {role}, Method {method}, URI {endpoint}: was "
                    f"expected to be allowed (200) not {response.status} "
                    f"{response.data}"
                )
        else:
            role = ServerRoles.CONTRIBUTOR

            response = do_call(
                app, method, endpoint, None, webhook_fixture, None
            )
            assert response.status_code == HTTPStatus.UNAUTHORIZED, (
                f"Role {role}, Method {method}, URI {endpoint}: was "
                f"expected to be unauthorized (401) not "
                f"{response.status} {response.data}"
            )

    @pytest.mark.parametrize("auth_type", ["bearer_header", None])
    def test_permissions_without_oidc_enabled(
        self,
        auth_scenario,
        app_with_store,
        auth_type,
        role_clients_factory,
        webhook_fixture,
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
        app = app_with_store
        endpoint = auth_scenario["endpoint"]
        method = auth_scenario["method"]
        allowed_roles = set(auth_scenario["required_role"])
        forbidden_roles = ALL_ROLES.difference(allowed_roles)

        if auth_type:
            # When OIDC is disabled and an access token is provided, verify
            # the expected roles are able to access this endpoint.

            # Verify that roles which are not permitted recieve 403 Forbidden
            for role in forbidden_roles:
                response = do_call(
                    app,
                    method,
                    endpoint,
                    role_clients_factory[role],
                    webhook_fixture,
                    auth_type,
                )
                assert response.status_code == HTTPStatus.FORBIDDEN, (
                    f"Role {role}, Method {method}, URI {endpoint}: was "
                    f"expected to be forbidden (403) not {response.status} "
                    f"{response.data}"
                )

            # Verify that roles which ARE permitted to access this endpoint are
            # allowed to use the endpoint normally.
            for role in allowed_roles:
                response = do_call(
                    app,
                    method,
                    endpoint,
                    role_clients_factory[role],
                    webhook_fixture,
                    auth_type,
                )
                assert response.status_code == HTTPStatus.OK, (
                    f"Role {role}, Method {method}, URI {endpoint}: was "
                    f"expected to be allowed (200) not {response.status} "
                    f"{response.data}"
                )
        else:
            # Verify anonymous access is treated as CONTRIBUTOR:
            role = ServerRoles.CONTRIBUTOR

            response = do_call(
                app,
                method,
                endpoint,
                None,
                webhook_fixture,
                None,
            )

            # Note: /secrets/ endpoints MUST have true authorization, not
            # just a role:
            if ("secret" in endpoint):
                 # no client_id known
                assert response.status_code == HTTPStatus.UNAUTHORIZED, (
                    f"Role {role}, Method {method}, URI {endpoint}: was "
                    f"expected to be unauthorized (401) not {response.status} "
                    f"{response.data}"
                )
            elif ServerRoles.CONTRIBUTOR in forbidden_roles:
                assert response.status_code == HTTPStatus.FORBIDDEN, (
                    f"Role {role}, Method {method}, URI {endpoint}: was "
                    f"expected to be forbidden (403) not {response.status} "
                    f"{response.data}"
                )
            else:  # allowed
                assert response.status_code == HTTPStatus.OK, (
                    f"Role {role}, Method {method}, URI {endpoint}: was "
                    f"expected to be allowed (200) not {response.status} "
                    f"{response.data}"
                )
