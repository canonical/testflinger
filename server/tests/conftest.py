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

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
import mongomock
import pytest
from mongomock.gridfs import enable_gridfs_integration
from testflinger_common.enums import ServerRoles

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
def mongo_app_fixture():
    """Create a pytest fixture for database and app."""
    mock_mongo = MongoClientMock()
    database.mongo = mock_mongo
    app = application.create_flask_app(TestingConfig)
    yield app.test_client(), mock_mongo.db


@pytest.fixture
def testapp():
    """Pytest fixture for just the app."""
    app = application.create_flask_app(TestingConfig)
    yield app


@pytest.fixture
def mongo_app_with_permissions(mongo_app):
    """
    Pytest fixture that adds permissions
    to the mock db for priority.
    """
    os.environ["JWT_SIGNING_KEY"] = "my_secret_key"
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
def oidc_app(oidc_client, mongo_app, iam_server):
    """Pytest fixture with OIDC app for web authentication tests."""
    _, mongo = mongo_app

    # Define OIDC variables for testing
    os.environ.update(
        {
            "OIDC_CLIENT_ID": oidc_client.client_id,
            "OIDC_CLIENT_SECRET": oidc_client.client_secret,
            "OIDC_PROVIDER_ISSUER": iam_server.url,
            "WEB_SECRET_KEY": "my_web_secret_key",
        }
    )

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
def agent_auth_header():
    """Create Authorization header with agent JWT token for GET /v1/job."""
    os.environ.setdefault("JWT_SIGNING_KEY", "my_secret_key")
    secret_key = os.environ["JWT_SIGNING_KEY"]
    token_payload = {
        "exp": datetime.now(timezone.utc) + timedelta(seconds=30),
        "iat": datetime.now(timezone.utc),
        "sub": "access_token",
        "permissions": {
            "client_id": "agent-test",
            "role": ServerRoles.AGENT,
        },
    }
    token = jwt.encode(token_payload, secret_key, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}
