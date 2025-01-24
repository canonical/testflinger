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
"""
Fixtures for testing
"""

import os

from dataclasses import dataclass
import pytest
import mongomock
from mongomock.gridfs import enable_gridfs_integration
import bcrypt

from src import database, application


@dataclass
class TestingConfig:
    """Config for Testing"""

    TESTING = True


class MongoClientMock(mongomock.MongoClient):
    """Mock MongoClient and allow GridFS"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        enable_gridfs_integration()

    def start_session(self, *args, **kwargs):
        # Reimplemented to avoid pylint issues
        return super().start_session(*args, **kwargs)


@pytest.fixture(name="mongo_app")
def mongo_app_fixture():
    """Create a pytest fixture for database and app"""
    mock_mongo = MongoClientMock()
    database.mongo = mock_mongo
    app = application.create_flask_app(TestingConfig)
    yield app.test_client(), mock_mongo.db


@pytest.fixture
def testapp():
    """pytest fixture for just the app"""
    app = application.create_flask_app(TestingConfig)
    yield app


@pytest.fixture
def mongo_app_with_permissions(mongo_app):
    """
    Pytest fixture that adds permissions
    to the mock db for priority
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
