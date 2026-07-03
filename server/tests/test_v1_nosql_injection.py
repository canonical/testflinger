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
"""Regression tests for MongoDB (NoSQL) operator-injection hardening.

These tests exercise endpoints that read untrusted request data and use it
in MongoDB queries. They ensure that attacker-supplied operator documents
(e.g. ``{"$ne": null}``) are rejected instead of being interpreted as query
operators or stored verbatim.
"""

from http import HTTPStatus

from testflinger_common.enums import ServerRoles

from tests.utilities import get_access_token_header


def test_refresh_rejects_operator_injection(mongo_app):
    """An operator document must not match an arbitrary refresh token.

    Regression test for an unauthenticated authentication-bypass: sending
    ``{"refresh_token": {"$ne": null}}`` previously matched a valid stored
    token via ``find_one`` and minted an access token for that client.
    """
    app, mongo = mongo_app
    mongo.refresh_tokens.insert_one(
        {
            "client_id": "victim-client",
            "refresh_token": "super-secret-token-value",
            "revoked": False,
        }
    )

    response = app.post(
        "/v1/oauth2/refresh",
        json={"refresh_token": {"$ne": None}},
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    # No access token must be issued
    assert "access_token" not in (response.get_json() or {})


def test_refresh_rejects_list_injection(mongo_app):
    """A non-string (list) refresh token must be rejected."""
    app, mongo = mongo_app
    mongo.refresh_tokens.insert_one(
        {
            "client_id": "victim-client",
            "refresh_token": "super-secret-token-value",
            "revoked": False,
        }
    )

    response = app.post(
        "/v1/oauth2/refresh",
        json={"refresh_token": ["super-secret-token-value"]},
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_revoke_rejects_operator_injection(mongo_app):
    """Revocation must not match/revoke an arbitrary token via an operator.

    Regression test: ``{"refresh_token": {"$ne": null}}`` previously revoked
    the first matching token, allowing an admin to disable arbitrary users'
    sessions without knowing their token.
    """
    app, mongo = mongo_app
    mongo.refresh_tokens.insert_one(
        {
            "client_id": "victim-client",
            "refresh_token": "super-secret-token-value",
            "revoked": False,
        }
    )
    admin_header = get_access_token_header("admin-id", ServerRoles.ADMIN)

    response = app.post(
        "/v1/oauth2/revoke",
        json={"refresh_token": {"$ne": None}},
        headers=admin_header,
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    # The victim token must remain un-revoked
    token = mongo.refresh_tokens.find_one(
        {"refresh_token": "super-secret-token-value"}
    )
    assert token["revoked"] is False


def test_queues_post_rejects_non_string_description(mongo_app):
    """queues_post must reject non-string descriptions.

    A rejected payload must not store an operator document.
    """
    app, mongo = mongo_app
    agent_header = get_access_token_header("agent-id", ServerRoles.AGENT)

    response = app.post(
        "/v1/agents/queues",
        json={"myqueue": {"$ne": None}},
        headers=agent_header,
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert mongo.queues.find_one({"name": "myqueue"}) is None


def test_queues_post_rejects_non_object_body(mongo_app):
    """queues_post must reject a non-object JSON body."""
    app, _ = mongo_app
    agent_header = get_access_token_header("agent-id", ServerRoles.AGENT)

    response = app.post(
        "/v1/agents/queues",
        json=["not", "an", "object"],
        headers=agent_header,
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_queues_post_accepts_valid_payload(mongo_app):
    """queues_post must still accept a normal payload (no regression)."""
    app, mongo = mongo_app
    agent_header = get_access_token_header("agent-id", ServerRoles.AGENT)

    response = app.post(
        "/v1/agents/queues",
        json={"myqueue": "a normal description"},
        headers=agent_header,
    )

    assert response.status_code == HTTPStatus.OK
    stored = mongo.queues.find_one({"name": "myqueue"})
    assert stored["description"] == "a normal description"


def test_images_post_rejects_non_string_provision_data(mongo_app):
    """images_post must reject operator documents in provision data."""
    app, mongo = mongo_app
    agent_header = get_access_token_header("agent-id", ServerRoles.AGENT)

    response = app.post(
        "/v1/agents/images",
        json={"myqueue": {"core22": {"$ne": None}}},
        headers=agent_header,
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert mongo.queues.find_one({"name": "myqueue"}) is None


def test_images_post_rejects_non_object_image_data(mongo_app):
    """images_post must reject non-object image data for a queue."""
    app, mongo = mongo_app
    agent_header = get_access_token_header("agent-id", ServerRoles.AGENT)

    response = app.post(
        "/v1/agents/images",
        json={"myqueue": {"$ne": None}},
        headers=agent_header,
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert mongo.queues.find_one({"name": "myqueue"}) is None


def test_images_post_accepts_valid_payload(mongo_app):
    """images_post must still accept a normal payload (no regression)."""
    app, mongo = mongo_app
    agent_header = get_access_token_header("agent-id", ServerRoles.AGENT)

    response = app.post(
        "/v1/agents/images",
        json={"myqueue": {"core22": "url: http://example/core22.img.xz"}},
        headers=agent_header,
    )

    assert response.status_code == HTTPStatus.OK
    stored = mongo.queues.find_one({"name": "myqueue"})
    assert stored["images"] == {"core22": "url: http://example/core22.img.xz"}


def test_search_jobs_rejects_invalid_state(mongo_app):
    """search_jobs must reject states outside the allowed set."""
    app, _ = mongo_app
    admin_header = get_access_token_header("admin-id", ServerRoles.ADMIN)

    response = app.get(
        "/v1/job/search?state=not_a_real_state",
        headers=admin_header,
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_search_jobs_valid_query_still_works(mongo_app):
    """search_jobs must still return results for a valid query."""
    app, mongo = mongo_app
    admin_header = get_access_token_header("admin-id", ServerRoles.ADMIN)
    mongo.jobs.insert_one(
        {
            "job_id": "11111111-1111-1111-1111-111111111111",
            "created_at": "2020-01-01",
            "result_data": {"job_state": "provision"},
            "job_data": {"job_queue": "q", "tags": ["t1"]},
        }
    )

    response = app.get(
        "/v1/job/search?state=provision&tags=t1&match=all",
        headers=admin_header,
    )

    assert response.status_code == HTTPStatus.OK
    body = response.get_json()
    assert len(body) == 1
    assert body[0]["job_id"] == "11111111-1111-1111-1111-111111111111"


def test_database_refresh_token_helpers_reject_non_string(mongo_app):
    """Defence-in-depth: DB helpers must never query with a non-string token.

    Even if a caller forgets to validate, ``get_refresh_token_by_token`` must
    not use an operator document as a filter operand.
    """
    from testflinger import database

    _app, mongo = mongo_app
    mongo.refresh_tokens.insert_one(
        {
            "client_id": "victim-client",
            "refresh_token": "super-secret-token-value",
            "revoked": False,
        }
    )

    assert database.get_refresh_token_by_token({"$ne": None}) is None
    # edit/delete with an operator must be a no-op
    database.edit_refresh_token({"$ne": None}, {"revoked": True})
    database.delete_refresh_token({"$ne": None})
    token = mongo.refresh_tokens.find_one(
        {"refresh_token": "super-secret-token-value"}
    )
    assert token is not None
    assert token["revoked"] is False
