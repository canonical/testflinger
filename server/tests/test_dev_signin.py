# Copyright (C) 2026 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
"""Tests for the development-only auto sign-in blueprint.

The route ``POST /auth/dev-signin`` MUST be disabled unless BOTH gates are
open:

1. The ``TF_DEV_AUTO_SIGNIN`` env var is set to ``"1"``.
2. OIDC is configured (``tf_app.oauth is not None``).

These tests prove the route is not exposed by default (env var unset) and
also that setting the env var alone -- without OIDC -- is insufficient.
"""

import secrets
from http import HTTPStatus

import pytest

from testflinger import application, database
from testflinger.dev_signin import (
    DEV_AUTO_SIGNIN_ENV_VAR,
    DEV_SIGNIN_IDENTITIES,
)
from tests.conftest import MongoClientMock, TestingConfig


def _make_app(monkeypatch, *, dev_signin_env=None, oidc=False):
    """Build a fresh Flask app with the requested gate configuration."""
    monkeypatch.setenv("JWT_SIGNING_KEY", secrets.token_urlsafe(32))
    monkeypatch.delenv(DEV_AUTO_SIGNIN_ENV_VAR, raising=False)
    if dev_signin_env is not None:
        monkeypatch.setenv(DEV_AUTO_SIGNIN_ENV_VAR, dev_signin_env)

    if oidc:
        # Minimum env for create_flask_app to instantiate an OAuth client.
        monkeypatch.setenv("OIDC_CLIENT_ID", "test-client")
        monkeypatch.setenv("OIDC_CLIENT_SECRET", "test-secret")
        monkeypatch.setenv("OIDC_PROVIDER_ISSUER", "http://localhost:9999")
        monkeypatch.setenv("WEB_SECRET_KEY", "test-web-secret")

    database.mongo = MongoClientMock()
    return application.create_flask_app(TestingConfig)


def test_dev_signin_route_not_registered_by_default(monkeypatch):
    """No env var, no OIDC: route must not exist."""
    app = _make_app(monkeypatch)

    # The blueprint should not be registered.
    assert "dev_signin" not in app.blueprints

    # And the URL must not resolve.
    response = app.test_client().get(
        "/auth/dev-signin?email=alice@example.com"
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_dev_signin_route_not_registered_without_oidc(monkeypatch):
    """Env var set but no OIDC: still disabled (double gate)."""
    app = _make_app(monkeypatch, dev_signin_env="1", oidc=False)

    assert app.oauth is None
    assert "dev_signin" not in app.blueprints

    response = app.test_client().get(
        "/auth/dev-signin?email=alice@example.com"
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize("env_value", ["", "0", "true", "yes", "TRUE"])
def test_dev_signin_route_not_registered_for_non_one_values(
    monkeypatch, env_value
):
    """Only the literal string "1" enables the route -- nothing else."""
    app = _make_app(monkeypatch, dev_signin_env=env_value, oidc=True)

    assert "dev_signin" not in app.blueprints

    response = app.test_client().get(
        "/auth/dev-signin?email=alice@example.com"
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_dev_signin_context_processor_reports_disabled(monkeypatch):
    """The template flag ``dev_auto_signin`` must be False by default."""
    app = _make_app(monkeypatch)

    with app.test_request_context("/"):
        # Merge all context processors the way Jinja would.
        context = {}
        for processor in app.template_context_processors[None]:
            context.update(processor())

    assert context["dev_auto_signin"] is False
    assert context["dev_signin_identities"] == []


def test_dev_signin_context_processor_reports_enabled(monkeypatch):
    """The template receives the identity picker when both gates are open."""
    app = _make_app(monkeypatch, dev_signin_env="1", oidc=True)

    with app.test_request_context("/"):
        context = {}
        for processor in app.template_context_processors[None]:
            context.update(processor())

    assert context["dev_auto_signin"] is True
    assert context["dev_signin_identities"] == DEV_SIGNIN_IDENTITIES


def test_dev_signin_requires_post(monkeypatch):
    """The state-changing sign-in endpoint must not accept GET requests."""
    app = _make_app(monkeypatch, dev_signin_env="1", oidc=True)

    response = app.test_client().get("/auth/dev-signin")

    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED


@pytest.mark.parametrize(
    "identity", DEV_SIGNIN_IDENTITIES, ids=lambda identity: identity["name"]
)
def test_dev_signin_establishes_identity_session_and_role(
    monkeypatch, identity
):
    """Each allowlisted identity creates a matching session and role entry."""
    app = _make_app(monkeypatch, dev_signin_env="1", oidc=True)
    client = app.test_client()

    response = client.post(
        "/auth/dev-signin", data={"email": identity["email"]}
    )

    assert response.status_code == HTTPStatus.FOUND
    assert response.location == "/"
    assert database.get_client_permissions(identity["email"]) == {
        "client_id": identity["email"],
        "sub": identity["sub"],
        "role": str(identity["role"]),
    }
    with client.session_transaction() as session:
        assert session["user"] == identity["name"]
        assert session["user_email"] == identity["email"]


def test_dev_signin_overwrites_existing_identity_role(monkeypatch):
    """The shortcut updates the existing OIDC identity's declared role."""
    identity = DEV_SIGNIN_IDENTITIES[0]
    app = _make_app(monkeypatch, dev_signin_env="1", oidc=True)
    database.mongo.db.client_permissions.insert_one(
        {
            "client_id": identity["email"],
            "sub": identity["sub"],
            "role": "contributor",
        }
    )

    response = app.test_client().post(
        "/auth/dev-signin", data={"email": identity["email"]}
    )

    assert response.status_code == HTTPStatus.FOUND
    assert database.mongo.db.client_permissions.count_documents({}) == 1
    assert database.get_client_permissions(identity["email"])["role"] == str(
        identity["role"]
    )


@pytest.mark.parametrize("email", ["", "eve@example.com"])
def test_dev_signin_rejects_unknown_identity(monkeypatch, email):
    """Missing or non-allowlisted identities must not create a session."""
    app = _make_app(monkeypatch, dev_signin_env="1", oidc=True)
    client = app.test_client()

    response = client.post("/auth/dev-signin", data={"email": email})

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert database.mongo.db.client_permissions.count_documents({}) == 0
    with client.session_transaction() as session:
        assert "user" not in session
        assert "user_email" not in session
