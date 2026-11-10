# Copyright (C) 2025 Canonical Ltd.
"""Unit tests for the retry_request helper."""

import logging
from http import HTTPStatus
from unittest.mock import MagicMock, call, patch

import pytest
import requests

from testflinger_cli.consts import DEFAULT_BACKOFF_BASE
from testflinger_cli.errors import NetworkError
from testflinger_cli.helpers import retry_request


def _response(status):
    response = MagicMock(spec=requests.Response)
    response.status_code = status
    return response


@pytest.fixture
def mock_sleep():
    """Avoid real waiting between retries."""
    with patch("testflinger_cli.helpers.time.sleep") as sleep:
        yield sleep


def test_success_first_try(mock_sleep):
    """A successful request is returned without waiting."""
    ok = _response(HTTPStatus.OK)
    request = MagicMock(return_value=ok)

    assert retry_request(request, "do thing") is ok
    request.assert_called_once()
    mock_sleep.assert_not_called()


@pytest.mark.parametrize(
    "failure",
    [
        requests.exceptions.Timeout(),
        requests.exceptions.ConnectionError(),
        _response(HTTPStatus.BAD_GATEWAY),
    ],
)
def test_transient_failure_then_success(mock_sleep, failure):
    """Transient failures are retried until the request succeeds."""
    ok = _response(HTTPStatus.OK)
    request = MagicMock(side_effect=[failure, ok])

    assert retry_request(request, "do thing") is ok
    assert request.call_count == 2
    mock_sleep.assert_called_once_with(DEFAULT_BACKOFF_BASE)


@pytest.mark.parametrize(
    "status",
    [
        HTTPStatus.BAD_REQUEST,
        HTTPStatus.UNAUTHORIZED,
        HTTPStatus.FORBIDDEN,
        HTTPStatus.NOT_FOUND,
    ],
)
def test_non_transient_status_not_retried(mock_sleep, status):
    """Non transient responses are returned for the caller to handle."""
    response = _response(status)
    request = MagicMock(return_value=response)

    assert retry_request(request, "do thing") is response
    request.assert_called_once()
    mock_sleep.assert_not_called()


def test_exhausted_retries_raise_and_log(mock_sleep, caplog):
    """NetworkError is raised and logged once retries are exhausted."""
    request = MagicMock(side_effect=requests.exceptions.Timeout("slow"))

    with caplog.at_level(logging.WARNING):
        with pytest.raises(NetworkError, match="do thing"):
            retry_request(request, "do thing", max_retries=3)

    assert request.call_count == 4
    assert "Giving up on do thing" in caplog.text
    assert "retrying in" in caplog.text


def test_exhausted_retries_on_status_raise(mock_sleep):
    """Persistent 5xx responses end in NetworkError."""
    request = MagicMock(return_value=_response(HTTPStatus.BAD_GATEWAY))

    with pytest.raises(NetworkError, match="HTTP 502"):
        retry_request(request, "do thing", max_retries=2)
    assert request.call_count == 3


def test_backoff_is_exponential_and_capped(mock_sleep):
    """Delays double on each retry up to max_delay."""
    request = MagicMock(side_effect=requests.exceptions.Timeout())

    with pytest.raises(NetworkError):
        retry_request(
            request, "do thing", max_retries=5, base_delay=2, max_delay=10
        )

    assert mock_sleep.call_args_list == [
        call(2),
        call(4),
        call(8),
        call(10),
        call(10),
    ]


def test_deadline_stops_retries(mock_sleep):
    """No retries are attempted when the next wait passes the deadline."""
    request = MagicMock(side_effect=requests.exceptions.Timeout())

    with patch("testflinger_cli.helpers.time.monotonic", return_value=100):
        with pytest.raises(NetworkError):
            retry_request(request, "do thing", deadline=101)

    request.assert_called_once()
    mock_sleep.assert_not_called()
