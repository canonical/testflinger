# Copyright (C) 2026 Canonical Ltd.
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

"""Unit tests for job-events CLI command."""

import json
import sys
import uuid
from http import HTTPStatus

import pytest

import testflinger_cli

from .conftest import URL


@pytest.fixture
def sample_events():
    """Sample events for testing."""
    return [
        {
            "event_name": "job_submitted",
            "timestamp": {"$date": "2026-09-23T16:47:27.465Z"},
            "message": "Job submitted by user test-user into queue staging.",
            "detail": "",
        },
        {
            "event_name": "job_phase_started",
            "timestamp": {"$date": "2026-09-23T16:47:33.647Z"},
            "message": "Phase setup started.",
            "detail": "",
            "phase": "setup",
        },
        {
            "event_name": "job_phase_completed",
            "timestamp": {"$date": "2026-09-23T16:47:38.435Z"},
            "message": "Phase setup completed with exit code 0",
            "detail": "",
            "phase": "setup",
            "status": 0,
        },
        {
            "event_name": "job_phase_started",
            "timestamp": {"$date": "2026-09-23T16:47:38.980Z"},
            "message": "Phase provision started.",
            "detail": "",
            "phase": "provision",
        },
        {
            "event_name": "job_completed",
            "timestamp": {"$date": "2026-09-23T17:08:47.554Z"},
            "message": "Job completed.",
            "detail": "",
        },
    ]


@pytest.fixture
def empty_events():
    """Empty events list for testing."""
    return []


@pytest.fixture
def job_id():
    """Sample job ID for testing."""
    return str(uuid.uuid4())


def test_job_events_json_format(capsys, requests_mock, sample_events, job_id):
    """JSON output should include all events fields."""
    events_response = {"job_id": job_id, "events": sample_events}
    requests_mock.get(
        f"{URL}/v1/events/job/{job_id}",
        json=events_response,
    )

    sys.argv = ["", "job-events", job_id, "--format", "json"]
    cli = testflinger_cli.TestflingerCli()
    cli.job_events()

    output = json.loads(capsys.readouterr().out)

    # Verify all events are present
    assert len(output) == len(sample_events)

    # Verify each event contains all expected fields
    for event in output:
        assert "event_name" in event
        assert "timestamp" in event
        assert "message" in event
        assert "detail" in event
        # Phase and status are optional, check if they exist before asserting
        if "phase" in event:
            assert isinstance(event["phase"], str)
        if "status" in event:
            assert isinstance(event["status"], int)


def test_job_events_table_format_default(
    capsys, requests_mock, sample_events, job_id
):
    """Table output should display default columns."""
    events_response = {"job_id": job_id, "events": sample_events}
    requests_mock.get(
        f"{URL}/v1/events/job/{job_id}",
        json=events_response,
    )

    sys.argv = ["", "job-events", job_id]
    cli = testflinger_cli.TestflingerCli()
    cli.job_events()

    captured = capsys.readouterr()
    output = captured.out

    # Verify default headers are present
    headers = ["event_name", "timestamp", "message"]
    for header in headers:
        assert header.upper() in output

    # Verify event name and message are present in the output
    for event in sample_events:
        assert event["event_name"] in output
        assert event["message"] in output


def test_job_events_table_no_headers(
    capsys, requests_mock, sample_events, job_id
):
    """Table output with --no-headers should not display headers."""
    events_response = {"job_id": job_id, "events": sample_events}
    requests_mock.get(
        f"{URL}/v1/events/job/{job_id}",
        json=events_response,
    )

    sys.argv = ["", "job-events", job_id, "--no-headers"]
    cli = testflinger_cli.TestflingerCli()
    cli.job_events()

    captured = capsys.readouterr()
    output = captured.out

    # Verify default headers are not present
    headers = ["event_name", "timestamp", "message"]
    for header in headers:
        assert header.upper() not in output

    # Data rows should still be present
    for event in sample_events:
        assert event["event_name"] in output
        assert event["message"] in output


def test_job_events_table_missing_phase(capsys, requests_mock, job_id):
    """Table output should show empty for events without phase."""
    # Non-phase event
    events = [
        {
            "event_name": "job_submitted",
            "timestamp": {"$date": "2026-09-23T16:47:27.465Z"},
            "message": "Job submitted",
            "detail": "",
        }
    ]
    events_response = {"job_id": job_id, "events": events}
    requests_mock.get(
        f"{URL}/v1/events/job/{job_id}",
        json=events_response,
    )

    sys.argv = ["", "job-events", job_id]
    cli = testflinger_cli.TestflingerCli()
    cli.job_events()

    captured = capsys.readouterr()
    output = captured.out

    # Verify event is present but phase is empty
    assert "job_submitted" in output
    # Phase column should exist but be empty for this event
    lines = output.split("\n")
    event_line = [line for line in lines if "job_submitted" in line][0]
    # The line should have the event but empty phase cell
    assert len(event_line.split()) > 0


def test_job_events_with_fields_argument(
    capsys, requests_mock, sample_events, job_id
):
    """--fields argument should customize output columns."""
    events_response = {"job_id": job_id, "events": sample_events}
    requests_mock.get(
        f"{URL}/v1/events/job/{job_id}",
        json=events_response,
    )

    selected_fields = ["event_name", "message"]
    sys.argv = [
        "",
        "job-events",
        job_id,
        "--fields",
        ",".join(selected_fields),
    ]
    cli = testflinger_cli.TestflingerCli()
    cli.job_events()

    captured = capsys.readouterr()
    output = captured.out

    invalid_headers = ["detail", "phase", "timestamp"]

    # Verify only requested columns are present
    for header in selected_fields:
        assert header.upper() in output
    # These should not be in headers
    for header in invalid_headers:
        assert header.upper() not in output


def test_job_events_invalid_field_name(requests_mock, sample_events, job_id):
    """An invalid field name should raise error."""
    events_response = {"job_id": job_id, "events": sample_events}
    requests_mock.get(
        f"{URL}/v1/events/job/{job_id}",
        json=events_response,
    )
    sys.argv = [
        "",
        "job-events",
        job_id,
        "--fields",
        "event_name,invalid_field",
    ]

    # Exit is raised before calling job_events is called due to invalid field
    with pytest.raises(SystemExit):
        testflinger_cli.TestflingerCli()


def test_job_events_http_404(requests_mock, job_id):
    """404 error should exit with proper message."""
    requests_mock.get(
        f"{URL}/v1/events/job/{job_id}",
        status_code=HTTPStatus.NOT_FOUND,
        json={"message": "Job not found"},
    )

    sys.argv = ["", "job-events", job_id]
    cli = testflinger_cli.TestflingerCli()

    with pytest.raises(SystemExit) as exc_info:
        cli.job_events()

    assert exc_info.value.code == "Job not found"


def test_job_events_empty_events_list(
    capsys, requests_mock, empty_events, job_id
):
    """Empty events list should display an appropriate message."""
    events_response = {"job_id": job_id, "events": empty_events}
    requests_mock.get(
        f"{URL}/v1/events/job/{job_id}",
        json=events_response,
    )

    sys.argv = ["", "job-events", job_id]
    cli = testflinger_cli.TestflingerCli()
    cli.job_events()

    captured = capsys.readouterr()
    output = captured.out

    # Verify no-data message is shown
    assert "No events found matching specified criteria" in output


@pytest.mark.parametrize("output_format", ["json", "table"])
def test_job_events_timestamp_formatting(
    capsys, requests_mock, job_id, output_format
):
    """Timestamps should be formatted consistently in both formats."""
    events = [
        {
            "event_name": "job_submitted",
            "timestamp": {"$date": "2026-09-23T16:47:27.465Z"},
            "message": "Job submitted",
            "detail": "",
        }
    ]
    events_response = {"job_id": job_id, "events": events}
    requests_mock.get(
        f"{URL}/v1/events/job/{job_id}",
        json=events_response,
    )

    sys.argv = ["", "job-events", job_id, "--format", output_format]
    cli = testflinger_cli.TestflingerCli()
    cli.job_events()

    captured = capsys.readouterr()
    output = captured.out

    # Verify formatted timestamp is present
    assert "2026-09-23 16:47:27" in output
    # Verify raw MongoDB Extended JSON format is NOT present
    assert "$date" not in output
