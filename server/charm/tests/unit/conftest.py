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
"""Fixtures for charm unit tests."""

import pytest
from ops import testing

from charm import TestflingerCharm

TESTFLINGER_CONTAINER = "testflinger"
MONGO_DB_REMOTE_DATA = {
    "endpoints": "mongodb:27017",
    "username": "testflinger",
    "password": "testflinger",
    "database": "testflinger_db",
    "uris": "mongodb://testflinger:testflinger@mongodb:27017/testflinger_db",
}
MONGO_KEY_VAULT_REMOTE_DATA = {
    "endpoints": "mongodb:27017",
    "username": "testflinger-keyvault",
    "password": "keyvault-pass",
    "database": "encryption",
    "uris": (
        "mongodb://testflinger-keyvault:keyvault-pass@mongodb:27017/encryption"
    ),
}


@pytest.fixture
def ctx() -> testing.Context:
    """Fixture for Charm context."""
    return testing.Context(TestflingerCharm)


@pytest.fixture
def make_state():
    """Build test States with configurable parameters."""

    def factory(
        can_connect: bool = True,
        config: dict | None = None,
        stored_key: str | None = None,
        leader: bool = True,
    ) -> testing.State:
        return testing.State(
            containers=[
                testing.Container(
                    name=TESTFLINGER_CONTAINER, can_connect=can_connect
                )
            ],
            leader=leader,
            relations=[
                testing.Relation(
                    endpoint="mongodb_client",
                    remote_app_name="mongodb",
                    remote_app_data=MONGO_DB_REMOTE_DATA,
                ),
                testing.Relation(
                    endpoint="mongodb_keyvault",
                    remote_app_name="mongodb",
                    remote_app_data=MONGO_KEY_VAULT_REMOTE_DATA,
                ),
            ],
            config=config or {},
            stored_states={
                testing.StoredState(
                    owner_path="TestflingerCharm",
                    name="_stored",
                    content={
                        "reldata": {},
                        "previous_master_key": stored_key or "",
                    },
                )
            },
        )

    return factory
