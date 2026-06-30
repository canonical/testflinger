# Copyright (C) 2022 Canonical
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
"""Fixtures for testing."""

from dataclasses import dataclass
from http import HTTPStatus
from typing import Dict

import bcrypt
import mongomock
import pytest
from mongomock.gridfs import enable_gridfs_integration
from testflinger_common.enums import ServerRoles

import tests.utilities as utilities
from testflinger import application, database


@dataclass
class TestingConfig:
    """Config for Testing."""

    TESTING = True


class MongoClientMock(mongomock.MongoClient):
    """Mock MongoClient and allow GridFS."""

    def __init__(self, *args, **kwargs):
        """Initialize the MongoClientMock instance."""
        super().__init__(*args, **kwargs)
        enable_gridfs_integration()

    def start_session(self, *args, **kwargs):
        """Start a client session."""
        # Reimplemented to avoid pylint issues
        return super().start_session(*args, **kwargs)


@pytest.fixture(name="mongo_app")
def mongo_app_fixture(monkeypatch):
    """Create a pytest fixture for database and app."""
    secret_key = "my_secret_key_But_I_am_tired_of_all_the_warnings_about_keys"  # noqa: S105
    monkeypatch.setenv("JWT_SIGNING_KEY", secret_key)
    mock_mongo = MongoClientMock()
    database.mongo = mock_mongo
    app = application.create_flask_app(TestingConfig)
    yield app.test_client(), mock_mongo.db


@pytest.fixture
def testapp(monkeypatch):
    """Pytest fixture for just the app."""
    secret_key = "my_secret_key_But_I_am_tired_of_all_the_warnings_about_keys"  # noqa: S105
    monkeypatch.setenv("JWT_SIGNING_KEY", secret_key)
    app = application.create_flask_app(TestingConfig)
    yield app


@pytest.fixture
def mongo_app_with_permissions(mongo_app):
    """
    Pytest fixture that adds permissions
    to the mock db for priority.
    """
    app, mongo = mongo_app
    client_id = "my_client_id"
    client_key = "my_client_key"
    client_salt = bcrypt.gensalt()
    client_key_hash = bcrypt.hashpw(
        client_key.encode("utf-8"), client_salt
    ).decode("utf-8")

    max_priority = {
        "*": 1,
        "myqueue": 100,
        "myqueue2": 200,
    }
    allowed_queues = ["rqueue1", "rqueue2"]
    max_reservation_time = {"myqueue": 30000}
    mongo.client_permissions.insert_one(
        {
            "client_id": client_id,
            "client_secret_hash": client_key_hash,
            "role": ServerRoles.ADMIN,
            "max_priority": max_priority,
            "allowed_queues": allowed_queues,
            "max_reservation_time": max_reservation_time,
        }
    )
    restricted_queues = [
        {"queue_name": "rqueue1"},
        {"queue_name": "rqueue2"},
        {"queue_name": "rqueue3"},
    ]
    mongo.restricted_queues.insert_many(restricted_queues)
    yield app, mongo, client_id, client_key, max_priority


@pytest.fixture
def oidc_app(oidc_client, mongo_app, iam_server, monkeypatch):
    """Pytest fixture with OIDC app for web authentication tests."""
    _, mongo = mongo_app

    # Define OIDC variables for testing
    monkeypatch.setenv("OIDC_CLIENT_ID", oidc_client.client_id)
    monkeypatch.setenv("OIDC_CLIENT_SECRET", oidc_client.client_secret)
    monkeypatch.setenv("OIDC_PROVIDER_ISSUER", iam_server.url)
    monkeypatch.setenv("WEB_SECRET_KEY", "my_web_secret_key")

    # Create Flask app with OIDC provider
    oidc_app = application.create_flask_app(TestingConfig)

    yield oidc_app, mongo


@pytest.fixture
def oidc_client(iam_server):
    """Pytest fixture with OIDC client for testing web authentication."""
    inst = iam_server.models.Client(
        client_id="my_oidc_client_id",
        client_secret="my-oidc-secret",  # noqa: S106
        client_name="Testflinger Test",
        client_uri="http://localhost:5000",
        redirect_uris=["http://localhost:5000/auth/callback"],
        grant_types=["authorization_code"],
        response_types=["code", "token", "id_token"],
        token_endpoint_auth_method="client_secret_basic",  # noqa: S106
        scope=["openid", "profile", "email"],
    )
    iam_server.backend.save(inst)
    yield inst
    iam_server.backend.delete(inst)


@pytest.fixture
def user(iam_server):
    """Pytest fixture for defining the OIDC users."""
    user = iam_server.models.User(
        user_name="testuser",
        emails=["email@example.com"],
        password="test_password",  # noqa: S106
    )
    iam_server.backend.save(user)
    yield user
    iam_server.backend.delete(user)


@pytest.fixture
def sorted_roles():
    """Roles listed from least to most privileged."""
    return [
        ServerRoles.AGENT,
        ServerRoles.CONTRIBUTOR,
        ServerRoles.MANAGER,
        ServerRoles.ADMIN,
    ]


@pytest.fixture
def agent_auth_header():
    """Pytest fixture that provides an Authorization header for an agent."""
    return utilities.get_access_token_header("agent-id", ServerRoles.AGENT)


@pytest.fixture
def role_clients_factory(mongo_app):
    """
    Fixture to create isolated test clients for each of the four roles.
    Each client returns: {id, key, basic_header}
    Uses mongomock so no data persists - pure unit testing mode.
    """
    _, mongo_db = mongo_app

    def _make_client(role: ServerRoles) -> dict:
        import uuid

        client_id = f"{role.value}_client_{uuid.uuid4().hex[:8]}"
        client_key = f"key_{role.value}_{uuid.uuid4()}.key_2"

        mongo_db.client_permissions.delete_many({})
        mongo_db.client_permissions.insert_one(
            {
                "client_id": client_id,
                "role": role,
                "max_priority": {},
                "allowed_queues": [],
                "max_reservation_time": {},
            }
        )

        return {
            "id": client_id,
            "key": client_key,
            "role": role,
            "basic_header": utilities.get_basic_auth_header(
                client_id, client_key
            ),
            "bearer_header": utilities.get_access_token_header(
                client_id, role
            ),
        }

    roles: Dict[ServerRoles, dict] = {}
    for role in ServerRoles:
        roles[role] = _make_client(role)
    return roles


@pytest.fixture
def webhook_fixture(requests_mock, monkeypatch):
    """Set up a working webhook for when we need it."""
    webhook = "http://mywebhook.com/v1/test-executions/1234/status_update"
    monkeypatch.setenv("WEBHOOK_URL", "http://mywebhook.com/")
    requests_mock.put(webhook, status_code=HTTPStatus.OK)
    return webhook
