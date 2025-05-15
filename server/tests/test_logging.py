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

"""Tests for storing/retrieving agent logs."""

import uuid
from datetime import datetime, timezone

import pytest
from testflinger_common.enums import LogType, TestPhase

from testflinger.log_handlers import MongoLogHandler


@pytest.fixture(name="mongo_app_with_outputs")
def fixture_mongo_app_with_outputs(mongo_app):
    """Fixture for a MongoDB object with initialized logs."""
    job_id = str(uuid.uuid1())
    app, mongo = mongo_app
    for i in range(10):
        # Add fragments with timestamp staggered by 5 minutes
        mongo.db.logs.insert_one(
            {
                "job_id": job_id,
                "log_type": str(LogType.STANDARD_OUTPUT),
                "phase": TestPhase.SETUP,
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
            "phase": TestPhase.SETUP,
            "fragment_number": i,
            "log_data": f"My log data {i}",
        }
        log_handler.store_log_fragment(
            job_id, log_data, LogType.STANDARD_OUTPUT
        )
    log_fragments = list(mongo.db.logs.find({"job_id": job_id}))
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
        job_id, LogType.STANDARD_OUTPUT, TestPhase.SETUP, start_fragment
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
        job_id,
        LogType.STANDARD_OUTPUT,
        TestPhase.SETUP,
        start_timestamp=start_timestamp,
    )
    assert len(fragments) == 3
    for i, f in enumerate(fragments):
        assert f["fragment_number"] == i + 7
        assert f["log_data"] == f"My log data {i + 7}"


def test_retrieve_logs(mongo_app_with_outputs):
    """Tests that combined logs can be retrieved using the log_handler."""
    _, mongo, job_id = mongo_app_with_outputs
    log_handler = MongoLogHandler(mongo)
    combined_log = log_handler.retrieve_logs(
        job_id, LogType.STANDARD_OUTPUT, TestPhase.SETUP, 0
    )
    combined_log_expected = "".join([f"My log data {i}" for i in range(10)])
    assert combined_log["last_fragment_number"] == 9
    assert combined_log["log_data"] == combined_log_expected


def test_output_post_get(mongo_app):
    """Test posting output data for a job then reading it back."""
    app, _ = mongo_app
    job_id = "00000000-0000-0000-0000-000000000000"
    output_url = f"/v1/result/{job_id}/log/output"
    log_data = "line1\nline2\nline3"
    timestamp = datetime(2020, 1, 1, tzinfo=timezone.utc).isoformat()
    phase = str(TestPhase.SETUP)
    log_json = {
        "fragment_number": 0,
        "timestamp": timestamp,
        "phase": phase,
        "log_data": log_data,
    }
    output = app.post(output_url, json=log_json)
    assert "OK" == output.text
    output = app.get(output_url)
    phase_output = output.json["phase_logs"][phase]
    assert phase_output["last_fragment_number"] == 0
    assert phase_output["log_data"] == log_data


def test_output_post_get_query(mongo_app):
    """Test output endpoints with timestamp querying."""
    app, _ = mongo_app
    job_id = "00000000-0000-0000-0000-000000000000"
    output_url = f"/v1/result/{job_id}/log/{LogType.STANDARD_OUTPUT}"
    phase = str(TestPhase.SETUP)
    for i in range(10):
        log_data = f"line{i}\n"
        timestamp = datetime(
            2025, 4, 24, 10, 5 * i, 0, tzinfo=timezone.utc
        ).isoformat()
        log_json = {
            "fragment_number": i,
            "timestamp": timestamp,
            "phase": phase,
            "log_data": log_data,
        }
        output = app.post(output_url, json=log_json)
        assert "OK" == output.text
    query_timestamp = datetime(
        2025, 4, 24, 10, 32, 0, tzinfo=timezone.utc
    ).isoformat()
    params = {"start_timestamp": query_timestamp, "phase": phase}
    encoded_params = urllib.parse.urlencode(params)
    url_with_timestamp = f"{output_url}?{encoded_params}"
    output = app.get(url_with_timestamp)
    combined_log_expected = "".join([f"line{i}\n" for i in range(7, 10)])
    assert output.status_code == 200
    phase_output = output.json["phase_logs"][phase]
    assert phase_output["log_data"] == combined_log_expected
    assert phase_output["last_fragment_number"] == 9


def test_output_post_get_phase_query(mongo_app):
    """Test output endpoints with phase querying."""
    app, _ = mongo_app
    job_id = "00000000-0000-0000-0000-000000000000"
    output_url = f"/v1/result/{job_id}/log/{LogType.STANDARD_OUTPUT}"
    phases = [str(TestPhase.SETUP), str(TestPhase.PROVISION)]
    for i in range(10):
        for phase in phases:
            log_data = f"{phase} line{i}\n"
            timestamp = datetime(
                2025, 4, 24, 10, 5 * i, 0, tzinfo=timezone.utc
            ).isoformat()
            log_json = {
                "fragment_number": i,
                "timestamp": timestamp,
                "phase": phase,
                "log_data": log_data,
            }
            output = app.post(output_url, json=log_json)
            assert "OK" == output.text
    query_timestamp = datetime(
        2025, 4, 24, 10, 32, 0, tzinfo=timezone.utc
    ).isoformat()
    phase = TestPhase.PROVISION
    params = {"start_timestamp": query_timestamp, "phase": phase}
    encoded_params = urllib.parse.urlencode(params)
    url_with_timestamp = f"{output_url}?{encoded_params}"
    output = app.get(url_with_timestamp)
    combined_log_expected = "".join(
        [f"{phase} line{i}\n" for i in range(7, 10)]
    )
    assert output.status_code == 200
    phase_output = output.json["phase_logs"][phase]
    assert phase_output["log_data"] == combined_log_expected
    assert phase_output["last_fragment_number"] == 9


def test_output_get_invalid_query(mongo_app):
    """Test output endpoint fails when given invalid timestamp."""
    app, _ = mongo_app
    job_id = "00000000-0000-0000-0000-000000000000"
    output_url = f"/v1/result/{job_id}/log/{LogType.STANDARD_OUTPUT}"
    params = {"start_timestamp": "my wrong timestamp"}
    encoded_params = urllib.parse.urlencode(params)
    url_with_timestamp = f"{output_url}?{encoded_params}"
    output = app.get(url_with_timestamp)
    assert output.status_code == 400


def test_serial_output(mongo_app):
    """Test api endpoint to get serial log output."""
    app, _ = mongo_app
    job_id = "00000000-0000-0000-0000-000000000000"
    output_url = f"/v1/result/{job_id}/log/{LogType.SERIAL_OUTPUT}"
    log_data = "line1\nline2\nline3"
    timestamp = datetime(2020, 1, 1, tzinfo=timezone.utc).isoformat()
    phase = str(TestPhase.SETUP)
    log_json = {
        "fragment_number": 0,
        "timestamp": timestamp,
        "phase": phase,
        "log_data": log_data,
    }
    output = app.post(output_url, json=log_json)
    assert "OK" == output.text
    output = app.get(output_url)
    phase_output = output.json["phase_logs"][phase]
    assert phase_output["last_fragment_number"] == 0
    assert phase_output["log_data"] == log_data
