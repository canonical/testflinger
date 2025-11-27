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
from http import HTTPStatus

import pytest
import requests

from testflinger_cli.client import Client, HTTPError
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
