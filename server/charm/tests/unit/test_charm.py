# Copyright (C) 2023 Canonical
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
Unit tests for Testflinger Juju charm
"""

from pathlib import Path

import ops
import ops.testing
import pytest

from charm import TestflingerCharm

CHARMDIR = Path(__file__).parent.parent.parent.resolve()


@pytest.fixture(name="harness")
def fixture_harness():
    """Pytest fixture for getting the harness"""
    harness = ops.testing.Harness(TestflingerCharm)
    return harness


def test_waiting_for_relation(harness):
    """Test that the status is set to waiting when relation is not present"""
    harness.begin()
    with pytest.raises(SystemExit):
        assert harness.container_pebble_ready("testflinger")
    assert isinstance(harness.model.unit.status, ops.WaitingStatus)


def test_good_relation_active_status(harness):
    """status should be active when the relation is present"""
    harness.container_pebble_ready("testflinger")
    harness.set_can_connect("testflinger", True)
    harness.begin()
    rel_id = harness.add_relation("mongodb_client", "mongodb")
    harness.update_relation_data(
        rel_id,
        "mongodb",
        {
            "port": "27017",
            "host": "mongodb",
            "username": "testflinger",
            "password": "testflinger",
            "database": "testflinger_db",
            "endpoints": "mongodb/0",
        },
    )
    assert isinstance(harness.model.unit.status, ops.ActiveStatus)


def test_remove_relation_waiting_status(harness):
    """status should be waiting when the relation is present"""
    harness.container_pebble_ready("testflinger")
    harness.set_can_connect("testflinger", True)
    harness.begin()
    rel_id = harness.add_relation("mongodb_client", "mongodb")
    harness.update_relation_data(
        rel_id,
        "mongodb",
        {
            "port": "27017",
            "host": "mongodb",
            "username": "testflinger",
            "password": "testflinger",
            "database": "testflinger_db",
            "endpoints": "mongodb/0",
        },
    )
    assert isinstance(harness.model.unit.status, ops.ActiveStatus)
    with pytest.raises(SystemExit):
        harness.remove_relation(rel_id)
    assert isinstance(harness.model.unit.status, ops.WaitingStatus)


def test_container_cant_connect_waiting_status(harness):
    """status should be waiting container can't connect"""
    harness.container_pebble_ready("testflinger")
    harness.set_can_connect("testflinger", False)
    harness.begin()
    rel_id = harness.add_relation("mongodb_client", "mongodb")
    harness.update_relation_data(
        rel_id,
        "mongodb",
        {
            "port": "27017",
            "host": "mongodb",
            "username": "testflinger",
            "password": "testflinger",
            "database": "testflinger_db",
            "endpoints": "mongodb/0",
        },
    )
    assert isinstance(harness.model.unit.status, ops.WaitingStatus)


def test_incomplete_relation_maintenance_status(harness):
    """status should be maintenance when relation data is incomplete"""
    harness.container_pebble_ready("testflinger")
    harness.set_can_connect("testflinger", False)
    harness.begin()
    rel_id = harness.add_relation("mongodb_client", "mongodb")
    harness.update_relation_data(
        rel_id,
        "mongodb",
        {
            "port": "27017",
            "host": "mongodb",
        },
    )
    assert isinstance(harness.model.unit.status, ops.MaintenanceStatus)
