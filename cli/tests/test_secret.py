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

"""Unit tests for secret commands from testflinger-cli."""

import sys
from http import HTTPStatus
from unittest.mock import mock_open, patch

import pytest

import testflinger_cli
from testflinger_cli.consts import DEFAULT_SECRET_EXPIRATION
from testflinger_cli.enums import ServerRoles

from .test_cli import URL


@pytest.mark.parametrize(
    "test_path",
    [
        "path",
        "my/secret/path",
        "path/1234",
        "my/1234/path",
        "my/secret-path",
        "my/1path",
        "my/secret_path",
    ],
)
def test_secret_write(auth_fixture, capsys, requests_mock, test_path):
    """Test successful secret write operation."""
    auth_fixture(ServerRoles.CONTRIBUTOR)
    test_value = "secret_value_123"

    requests_mock.put(
        f"{URL}/v1/secrets/my_client_id/{test_path}",
        json={"expires_at": "2027-01-01T00:00:00+00:00"},
        status_code=HTTPStatus.OK,
    )

    sys.argv = [
        "",
        "secret",
        "write",
        test_path,
        test_value,
    ]

    testflinger_cli.TestflingerCli().run()

    std = capsys.readouterr()
    assert f"Secret '{test_path}' written successfully" in std.out
    assert "This secret will expire at 2027-01-01 00:00:00 UTC" in std.out

    # Verify the request was made with correct data
    last_request = requests_mock.last_request
    assert last_request.json() == {
        "value": test_value,
        "expire_after": DEFAULT_SECRET_EXPIRATION,
    }


def test_secret_write_http_error(auth_fixture, requests_mock):
    """Test secret write with HTTP error."""
    auth_fixture(ServerRoles.CONTRIBUTOR)
    test_path = "my/secret/path"
    test_value = "secret_value_123"

    requests_mock.put(
        f"{URL}/v1/secrets/my_client_id/{test_path}",
        json={"message": "Access denied"},
        status_code=HTTPStatus.FORBIDDEN,
    )

    sys.argv = [
        "",
        "secret",
        "write",
        test_path,
        test_value,
    ]

    tfcli = testflinger_cli.TestflingerCli()
    with pytest.raises(SystemExit) as exc_info:
        tfcli.run()

    assert "Error writing secret: [403] Access denied" in str(exc_info.value)


@pytest.mark.parametrize(
    "test_path",
    [
        "path",
        "my/secret/path",
        "path/1234",
        "my/1234/path",
        "my/secret-path",
        "my/1path",
        "my/secret_path",
    ],
)
def test_secret_delete(auth_fixture, capsys, requests_mock, test_path):
    """Test successful secret delete operation."""
    auth_fixture(ServerRoles.CONTRIBUTOR)

    requests_mock.delete(
        f"{URL}/v1/secrets/my_client_id/{test_path}",
        text="OK",
        status_code=HTTPStatus.OK,
    )

    sys.argv = [
        "",
        "secret",
        "delete",
        test_path,
    ]

    testflinger_cli.TestflingerCli().run()

    std = capsys.readouterr()
    assert f"Secret '{test_path}' deleted successfully" in std.out


def test_secret_delete_http_error(auth_fixture, requests_mock):
    """Test secret delete with HTTP error."""
    auth_fixture(ServerRoles.CONTRIBUTOR)
    test_path = "my/secret/path"

    requests_mock.delete(
        f"{URL}/v1/secrets/my_client_id/{test_path}",
        json={"message": "Secret not found"},
        status_code=HTTPStatus.NOT_FOUND,
    )

    sys.argv = [
        "",
        "secret",
        "delete",
        test_path,
    ]

    tfcli = testflinger_cli.TestflingerCli()
    with pytest.raises(SystemExit) as exc_info:
        tfcli.run()

    assert "Error deleting secret: [404] Secret not found" in str(
        exc_info.value
    )


@pytest.mark.parametrize("subcommand", ["write", "delete"])
def test_secret_no_authentication(subcommand):
    """Test secret operations fail when authentication is not configured."""
    if subcommand == "write":
        sys.argv = ["", "secret", "write", "test/path", "test_value"]
    else:
        sys.argv = ["", "secret", "delete", "test/path"]

    tfcli = testflinger_cli.TestflingerCli()
    with pytest.raises(SystemExit) as exc_info:
        tfcli.run()

    assert "Authentication is required" in str(exc_info.value)


@pytest.mark.parametrize("subcommand", ["write", "delete"])
@pytest.mark.parametrize(
    "status_code,error_message,expected_text",
    [
        (
            HTTPStatus.UNAUTHORIZED,
            "Invalid credentials",
            "Authentication with Testflinger server failed",
        ),
        (
            HTTPStatus.FORBIDDEN,
            "Insufficient permissions",
            "Authorization error received from server",
        ),
    ],
)
def test_secret_auth_errors(
    monkeypatch,
    requests_mock,
    subcommand,
    status_code,
    error_message,
    expected_text,
):
    """Test secret operations fail with authentication/authorization errors."""
    monkeypatch.setenv("TESTFLINGER_CLIENT_ID", "test_client")
    monkeypatch.setenv("TESTFLINGER_SECRET_KEY", "test_secret")

    # Mock authentication to fail
    requests_mock.post(
        f"{URL}/v1/oauth2/token",
        json={"message": error_message},
        status_code=status_code,
    )

    if subcommand == "write":
        sys.argv = ["", "secret", "write", "test/path", "test_value"]
    else:
        sys.argv = ["", "secret", "delete", "test/path"]

    tfcli = testflinger_cli.TestflingerCli()
    with pytest.raises(SystemExit) as exc_info:
        tfcli.run()

    assert expected_text in str(exc_info.value)


@pytest.mark.parametrize("subcommand", ["write", "delete"])
@patch(
    "builtins.open",
    mock_open(read_data="[AUTH]\nrefresh_token = expired_token\n"),
)
def test_secret_invalid_token_error(requests_mock, subcommand):
    """Test secret operations fail with invalid token error during refresh."""
    # Mock refresh endpoint to fail
    requests_mock.post(
        f"{URL}/v1/oauth2/refresh",
        text="Refresh token expired",
        status_code=HTTPStatus.BAD_REQUEST,
    )

    if subcommand == "write":
        sys.argv = ["", "secret", "write", "test/path", "test_value"]
    else:
        sys.argv = ["", "secret", "delete", "test/path"]

    tfcli = testflinger_cli.TestflingerCli()
    with pytest.raises(SystemExit) as exc_info:
        tfcli.run()

    assert "Please reauthenticate with server" in str(exc_info.value)


@pytest.mark.parametrize("expiration", [60, 3600, 86400])
def test_secret_write_with_expiration(
    auth_fixture, capsys, requests_mock, expiration
):
    """Test secret write sends correct expire_after value in request body."""
    auth_fixture(ServerRoles.CONTRIBUTOR)
    test_path = "my/secret/path"

    requests_mock.put(
        f"{URL}/v1/secrets/my_client_id/{test_path}",
        json={"expires_at": "2027-06-01T12:00:00+00:00"},
        status_code=HTTPStatus.OK,
    )

    sys.argv = [
        "",
        "secret",
        "write",
        test_path,
        "secret_value",
        "--expire-after",
        str(expiration),
    ]

    testflinger_cli.TestflingerCli().run()

    std = capsys.readouterr()
    assert "This secret will expire at 2027-06-01 12:00:00 UTC" in std.out
    assert requests_mock.last_request.json() == {
        "value": "secret_value",
        "expire_after": expiration,
    }


def test_secret_write_no_expiration(auth_fixture, capsys, requests_mock):
    """Test expire-after -1 sets None in expire_after in the request body."""
    auth_fixture(ServerRoles.CONTRIBUTOR)
    test_path = "my/secret/path"

    requests_mock.put(
        f"{URL}/v1/secrets/my_client_id/{test_path}",
        json={"expires_at": None},
        status_code=HTTPStatus.OK,
    )

    sys.argv = [
        "",
        "secret",
        "write",
        test_path,
        "secret_value",
        "--expire-after",
        "-1",
    ]

    testflinger_cli.TestflingerCli().run()

    std = capsys.readouterr()
    assert "This secret will not expire automatically" in std.out
    assert requests_mock.last_request.json() == {
        "value": "secret_value",
        "expire_after": None,
    }


def test_secret_write_single_use(auth_fixture, capsys, requests_mock):
    """Test that single-use sets the ephemeral flag in the request body."""
    auth_fixture(ServerRoles.CONTRIBUTOR)
    test_path = "my/secret/path"

    requests_mock.put(
        f"{URL}/v1/secrets/my_client_id/{test_path}",
        json={"expires_at": None},
        status_code=HTTPStatus.OK,
    )

    sys.argv = [
        "",
        "secret",
        "write",
        test_path,
        "secret_value",
        "--single-use",
    ]

    testflinger_cli.TestflingerCli().run()

    std = capsys.readouterr()
    assert "This secret will not expire automatically" in std.out
    assert requests_mock.last_request.json() == {
        "value": "secret_value",
        "ephemeral": True,
    }


def test_secret_write_single_use_and_expire_after_are_mutually_exclusive(
    auth_fixture, capsys
):
    """Test that single-use and expire-after cannot be used together."""
    auth_fixture(ServerRoles.CONTRIBUTOR)

    sys.argv = [
        "",
        "secret",
        "write",
        "my/secret/path",
        "secret_value",
        "--single-use",
        "--expire-after",
        "3600",
    ]

    with pytest.raises(SystemExit) as exc_info:
        testflinger_cli.TestflingerCli().run()

    assert exc_info.value.code == 2
    assert "not allowed with argument" in capsys.readouterr().err


@pytest.mark.parametrize(
    "test_path",
    [
        "/path",
        "/my/secret/path/",
        "invalid//path",
        "invalid path",
        "invalid\\path",
        "/////path",
        "path//////",
    ],
)
def test_secret_write_invalid_path(auth_fixture, capsys, test_path):
    """Test write operation is aborted for invalid paths."""
    auth_fixture(ServerRoles.CONTRIBUTOR)
    sys.argv = [
        "",
        "secret",
        "write",
        test_path,
        "test_value",
    ]
    with pytest.raises(SystemExit) as exc_info:
        testflinger_cli.TestflingerCli().run()

    # Argparse exits with code 2 for argument errors
    assert exc_info.value.code == 2
    assert (
        f"Invalid value '{test_path}', not a valid path"
        in capsys.readouterr().err
    )
