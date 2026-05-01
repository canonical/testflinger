# Copyright 2026 Canonical
# See LICENSE file for licensing details.

import json
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests
import testflinger_client
from defaults import DEFAULT_TOKEN_PATH

TEST_SERVER = "http://testflinger.local"


@patch("testflinger_client.write_file")
@patch("testflinger_client.Path.mkdir")
@patch("testflinger_client.requests.post")
def test_authenticate_success(mock_post, mock_mkdir, mock_write_file):
    """Test successful authentication returns True."""
    mock_response = MagicMock()
    mock_response.status_code = HTTPStatus.OK
    mock_response.json.return_value = {
        "access_token": "token123",
        "refresh_token": "refresh123",
    }
    mock_post.return_value = mock_response

    result = testflinger_client.authenticate(
        server=TEST_SERVER,
        client_id="test-client",
        secret_key="test-secret",  # noqa: S106
    )

    assert result is True
    mock_write_file.assert_called_once()

    args, _ = mock_write_file.call_args
    assert args[0] == Path(DEFAULT_TOKEN_PATH)

    written_data = json.loads(args[1])
    assert written_data["refresh_token"] == "refresh123"  # noqa: S105
    assert "obtained_at" in written_data


@patch("testflinger_client.requests.post")
def test_authenticate_failure(mock_post):
    """Test failed authentication returns False."""
    mock_response = MagicMock()
    mock_response.status_code = HTTPStatus.UNAUTHORIZED
    mock_post.return_value = mock_response

    result = testflinger_client.authenticate(
        server=TEST_SERVER,
        client_id="test-client",
        secret_key="test-secret",  # noqa: S106
    )

    assert result is False


@patch("testflinger_client.requests.post")
def test_authenticate_connection_error(mock_post):
    """Test authentication handles connection error."""
    mock_post.side_effect = requests.exceptions.ConnectionError()

    result = testflinger_client.authenticate(
        server=TEST_SERVER,
        client_id="test-client",
        secret_key="test-secret",  # noqa: S106
    )

    assert result is False


@patch("testflinger_client.Path.read_text")
@patch("testflinger_client.Path.exists")
def test_get_token_data_success(mock_exists, mock_read_text):
    """Test get_token_data returns parsed JSON when file exists."""
    mock_exists.return_value = True
    token_data = {
        "refresh_token": "token123",
        "obtained_at": datetime.now(timezone.utc).isoformat(),
    }
    mock_read_text.return_value = json.dumps(token_data)

    result = testflinger_client.get_token_data()

    assert result == token_data


@patch("testflinger_client.get_token_data")
def test_token_update_needed_no_token(mock_get_token_data):
    """Test token_update_needed returns True when no token exists."""
    mock_get_token_data.return_value = None

    result = testflinger_client.token_update_needed()

    assert result is True


@patch("testflinger_client.get_token_data")
def test_token_update_needed_valid_token(mock_get_token_data):
    """Test token_update_needed when token was recently obtained."""
    mock_get_token_data.return_value = {
        "refresh_token": "token123",
        "obtained_at": datetime.now(timezone.utc).isoformat(),
    }

    result = testflinger_client.token_update_needed()

    assert result is False


@patch("testflinger_client.get_token_data")
def test_token_update_needed(mock_get_token_data):
    """Test token_update_needed when token is older than 7 days."""
    old_date = datetime.now(timezone.utc) - timedelta(days=7, minutes=5)
    mock_get_token_data.return_value = {
        "refresh_token": "token123",
        "obtained_at": old_date.isoformat(),
    }

    result = testflinger_client.token_update_needed()

    assert result is True


@patch("testflinger_client.get_token_data")
def test_token_update_not_needed(mock_get_token_data):
    """Test token_update_needed when token is older than 7 days."""
    old_date = datetime.now(timezone.utc) - timedelta(days=6)
    mock_get_token_data.return_value = {
        "refresh_token": "token123",
        "obtained_at": old_date.isoformat(),
    }

    result = testflinger_client.token_update_needed()

    assert result is False
