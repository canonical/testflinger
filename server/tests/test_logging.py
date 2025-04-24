# Copyright (C) 2025 Canonical
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

"""Tests for storing/retrieving agent output and serial output."""

import uuid
from datetime import datetime, timezone

import pytest

from testflinger.log_handlers import LogType, MongoLogHandler


@pytest.fixture(name="mongo_app_with_outputs")
def fixture_mongo_app_with_outputs(mongo_app):
    """Fixture for a MongoDB object with initialized logs."""
    job_id = str(uuid.uuid1())
    app, mongo = mongo_app
    for i in range(10):
        # Add fragments with timestamp staggered by 5 minutes
        mongo.db.logs.output_fragments.insert_one(
            {
                "job_id": job_id,
                "fragment_number": i,
                "timestamp": datetime(
                    2025, 4, 24, 10, 5 * i, 0, tzinfo=timezone.utc
                ),
                "log_data": f"My log data {i}",
            }
        )
    yield app, mongo, job_id


def test_store_log_fragment(mongo_app):
    """Tests that log fragments can be stored using the log_handler."""
    _, mongo = mongo_app
    job_id = str(uuid.uuid1())
    log_handler = MongoLogHandler(mongo)
    for i in range(2):
        log_data = {
            "fragment_number": i,
            "log_data": f"My log data {i}",
        }
        log_handler.store_log_fragment(job_id, log_data, LogType.NORMAL_OUTPUT)
    log_fragments = list(
        mongo.db.logs.output_fragments.find({"job_id": job_id})
    )
    assert len(log_fragments) == 2
    assert log_fragments[0]["fragment_number"] == 0
    assert log_fragments[0]["log_data"] == "My log data 0"
    assert log_fragments[1]["fragment_number"] == 1
    assert log_fragments[1]["log_data"] == "My log data 1"


def test_retrieve_log_fragments(mongo_app_with_outputs):
    """Tests that log fragments can be retrieved using the log_handler."""
    _, mongo, job_id = mongo_app_with_outputs
    log_handler = MongoLogHandler(mongo)
    start_fragment = 5
    fragments = log_handler.retrieve_log_fragments(
        job_id, LogType.NORMAL_OUTPUT, start_fragment
    )
    assert len(fragments) == 5
    for i, f in enumerate(fragments):
        assert f["fragment_number"] == i + 5
        assert f["log_data"] == f"My log data {i + 5}"


def test_retrieve_log_fragments_by_timestamp(mongo_app_with_outputs):
    """
    Tests that log fragments can be retrieved using the log_handler
    when using timestamps.
    """
    _, mongo, job_id = mongo_app_with_outputs
    log_handler = MongoLogHandler(mongo)
    start_timestamp = datetime(2025, 4, 24, 10, 32, 0, tzinfo=timezone.utc)
    fragments = log_handler.retrieve_log_fragments(
        job_id, LogType.NORMAL_OUTPUT, start_timestamp=start_timestamp
    )
    assert len(fragments) == 3
    for i, f in enumerate(fragments):
        assert f["fragment_number"] == i + 7
        assert f["log_data"] == f"My log data {i + 7}"


def test_retrieve_logs(mongo_app_with_outputs):
    """Tests that combined logs can be retrieved using the log_handler."""
    _, mongo, job_id = mongo_app_with_outputs
    log_handler = MongoLogHandler(mongo)
    combined_log = log_handler.retrieve_logs(job_id, LogType.NORMAL_OUTPUT, 0)
    combined_log_expected = "".join([f"My log data {i}" for i in range(10)])
    assert combined_log["last_fragment_number"] == 9
    assert combined_log["log_data"] == combined_log_expected
