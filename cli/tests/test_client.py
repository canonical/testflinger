# Copyright (C) 2024 Canonical
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

"""Unit tests for the Client class."""

import logging
import urllib.parse
from datetime import datetime, timezone
from http import HTTPStatus

import pytest
import requests

from testflinger_cli.client import Client, HTTPError
from testflinger_cli.enums import LogType, TestPhase

from .test_cli import URL


def test_get_error_threshold(caplog, requests_mock):
    """Test that a warning is logged when error_threshold is reached."""
    caplog.set_level(logging.WARNING)
    requests_mock.get(
        "http://testflinger/test", exc=requests.exceptions.ConnectionError
    )
    client = Client("http://testflinger", error_threshold=3)
    for _ in range(2):
        with pytest.raises(requests.exceptions.ConnectionError):
            client.get("test")
        assert (
            "Error communicating with the server for the past"
            not in caplog.text
        )
    with pytest.raises(requests.exceptions.ConnectionError):
        client.get("test")
    assert (
        "Error communicating with the server for the past 3 requests"
        in caplog.text
    )


@pytest.mark.parametrize("method", ["post", "put", "delete"])
@pytest.mark.parametrize(
    "exception",
    [requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError],
)
def test_client_connection_errors_exit(requests_mock, method, exception):
    """Test that POST, PUT, DELETE methods exit on connection errors."""
    getattr(requests_mock, method)(f"{URL}/test", exc=exception)

    client = Client(URL)
    client_method = getattr(client, method)

    with pytest.raises(SystemExit) as exc_info:
        if method in ["post", "put"]:
            client_method("test", {"key": "value"})
        else:
            client_method("test")

    assert exc_info.value.code == 1


@pytest.mark.parametrize("method", ["get", "post", "put", "delete"])
def test_client_request_methods(requests_mock, method):
    """Test a successful request sent to server."""
    getattr(requests_mock, method)(f"{URL}/test", text="success")

    client = Client(URL)
    client_method = getattr(client, method)

    if method in ["post", "put"]:
        response = client_method("test", {"key": "value"})
    else:
        response = client_method("test")

    assert response == "success"


@pytest.mark.parametrize("method", ["get", "post", "put", "delete"])
def test_client_request_methods_schema_validation(requests_mock, method):
    """Test output from request after a schema validation fails."""
    validation_error_response = {
        "message": "Validation error",
        "detail": {
            "json": {
                "field1": "This field is required",
                "field2": "Invalid value provided",
            }
        },
    }

    getattr(requests_mock, method)(
        f"{URL}/test",
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        json=validation_error_response,
    )

    client = Client(URL)
    client_method = getattr(client, method)

    with pytest.raises(HTTPError) as exc_info:
        if method in ["post", "put"]:
            client_method("test", {"key": "value"})
        else:
            client_method("test")

    assert exc_info.value.status == HTTPStatus.UNPROCESSABLE_ENTITY
    error_details = ", ".join(
        [
            f"{field}: {msg}"
            for field, msg in validation_error_response["detail"][
                "json"
            ].items()
        ]
    )
    assert f"Validation error - {error_details}" == exc_info.value.msg


def test_get_logs_normal_output(requests_mock):
    """Test get_logs method for normal output."""
    job_id = "test-job-123"
    mock_response = {
        "output": {
            "test": {
                "last_fragment_number": 10,
                "log_data": "test output logs",
            }
        }
    }

    requests_mock.get(
        f"http://testflinger/v1/result/{job_id}/log/output?start_fragment=0",
        json=mock_response,
    )

    client = Client("http://testflinger")
    result = client.get_logs(job_id, LogType.STANDARD_OUTPUT, None, 0, None)

    assert result == mock_response


def test_get_logs_serial_output(requests_mock):
    """Test get_logs method for serial output."""
    job_id = "test-job-456"
    mock_response = {
        "serial": {
            "provision": {
                "last_fragment_number": 5,
                "log_data": "serial logs from provision",
            }
        }
    }

    requests_mock.get(
        f"http://testflinger/v1/result/{job_id}/log/serial_output?start_fragment=0",
        json=mock_response,
    )

    client = Client("http://testflinger")
    result = client.get_logs(job_id, LogType.SERIAL_OUTPUT, None, 0, None)

    assert result == mock_response


def test_get_logs_with_start_fragment(requests_mock):
    """Test get_logs method with start_fragment parameter."""
    job_id = "test-job-789"
    start_fragment = 15
    mock_response = {
        "output": {
            "test": {"last_fragment_number": 20, "log_data": "partial logs"}
        }
    }

    requests_mock.get(
        f"http://testflinger/v1/result/{job_id}/log/output?start_fragment={start_fragment}",
        json=mock_response,
    )

    client = Client("http://testflinger")
    result = client.get_logs(
        job_id, LogType.STANDARD_OUTPUT, None, start_fragment, None
    )

    assert result == mock_response


def test_get_logs_with_timestamp(requests_mock):
    """Test get_logs method with start_timestamp parameter."""
    job_id = "test-job-timestamp"
    start_timestamp = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    encoded_timestamp = urllib.parse.quote("2023-01-01T12:00:00+00:00")

    mock_response = {
        "output": {
            "test": {"last_fragment_number": 8, "log_data": "timestamped logs"}
        }
    }

    requests_mock.get(
        f"http://testflinger/v1/result/{job_id}/log/output?start_fragment=0&start_timestamp={encoded_timestamp}",
        json=mock_response,
    )

    client = Client("http://testflinger")
    result = client.get_logs(
        job_id, LogType.STANDARD_OUTPUT, None, 0, start_timestamp
    )

    assert result == mock_response


def test_get_logs_with_phase_filter(requests_mock):
    """Test get_logs method with phase filter."""
    job_id = "test-job-phase"
    phase = TestPhase.PROVISION

    mock_response = {
        "output": {
            "provision": {
                "last_fragment_number": 12,
                "log_data": "provision phase logs only",
            },
        }
    }

    requests_mock.get(
        f"http://testflinger/v1/result/{job_id}/log/output?start_fragment=0&phase={phase}",
        json=mock_response,
    )

    client = Client("http://testflinger")
    result = client.get_logs(job_id, LogType.STANDARD_OUTPUT, phase, 0, None)
    assert result == mock_response


def test_get_logs_with_all_parameters(requests_mock):
    """Test get_logs method with all parameters."""
    job_id = "test-job-all-params"
    phase = TestPhase.TEST
    start_fragment = 25
    start_timestamp = datetime(2023, 6, 15, 9, 30, 0, tzinfo=timezone.utc)
    encoded_timestamp = urllib.parse.quote("2023-06-15T09:30:00+00:00")

    mock_response = {
        "serial": {
            "test": {
                "last_fragment_number": 30,
                "log_data": "comprehensive test logs",
            }
        }
    }

    requests_mock.get(
        f"http://testflinger/v1/result/{job_id}/log/serial_output?start_fragment={start_fragment}&start_timestamp={encoded_timestamp}",
        json=mock_response,
    )

    client = Client("http://testflinger")
    result = client.get_logs(
        job_id, LogType.SERIAL_OUTPUT, phase, start_fragment, start_timestamp
    )

    assert result == mock_response


def test_get_logs_error_handling(requests_mock):
    """Test get_logs method error handling."""
    job_id = "test-job-error"

    requests_mock.get(
        f"http://testflinger/v1/result/{job_id}/log/output?start_fragment=0",
        status_code=404,
    )

    client = Client("http://testflinger")

    with pytest.raises(HTTPError):
        client.get_logs(job_id, LogType.STANDARD_OUTPUT, None, 0, None)
