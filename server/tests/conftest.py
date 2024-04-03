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

from dataclasses import dataclass
import pytest
import mongomock
from mongomock.gridfs import enable_gridfs_integration

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


@pytest.fixture
def mongo_app():
    """Create a pytest fixture for the app"""
    mock_mongo = MongoClientMock()
    database.mongo = mock_mongo
    app = application.create_flask_app(TestingConfig)
    yield app.test_client(), mock_mongo.db


@pytest.fixture
def testing_app():
    """Create an app for testing without using test_client"""
    app = application.create_flask_app(TestingConfig)
    yield app
