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

import pytest

import testflinger_cli
from testflinger_cli.consts import ServerRoles
from .test_cli import URL


def test_secret_write_success(auth_fixture, capsys, requests_mock):
    """Test successful secret write operation."""
    auth_fixture(ServerRoles.CONTRIBUTOR)
    test_path = "my/secret/path"
    test_value = "secret_value_123"

    requests_mock.put(
        f"{URL}/v1/secrets/my_client_id/{test_path}",
        text="OK",
        status_code=HTTPStatus.OK,
    )

    sys.argv = [
        "",
        "secret",
        "write",
        test_path,
        test_value,
    ]

    tfcli = testflinger_cli.TestflingerCli()
    tfcli.secret_write()

    std = capsys.readouterr()
    assert f"Secret '{test_path}' written successfully" in std.out

    # Verify the request was made with correct data
    last_request = requests_mock.last_request
    assert last_request.json() == {"value": test_value}


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
        tfcli.secret_write()

    assert "Error writing secret: [403] Access denied" in str(exc_info.value)


def test_secret_delete_success(auth_fixture, capsys, requests_mock):
    """Test successful secret delete operation."""
    auth_fixture(ServerRoles.CONTRIBUTOR)
    test_path = "my/secret/path"

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

    tfcli = testflinger_cli.TestflingerCli()
    tfcli.secret_delete()

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
        tfcli.secret_delete()

    assert "Error deleting secret: [404] Secret not found" in str(
        exc_info.value
    )


def test_secret_write_no_client_id(monkeypatch, requests_mock):
    """Test secret write fails when no client_id is configured."""
    # Don't set any environment variables for client_id
    sys.argv = [
        "",
        "secret",
        "write",
        "test/path",
        "test_value",
    ]

    tfcli = testflinger_cli.TestflingerCli()

    with pytest.raises(SystemExit) as exc_info:
        tfcli.secret_write()

    assert "Client ID is required for secret operations" in str(exc_info.value)


def test_secret_delete_no_client_id(monkeypatch, requests_mock):
    """Test secret delete fails when no client_id is configured."""
    # Don't set any environment variables for client_id
    sys.argv = [
        "",
        "secret",
        "delete",
        "test/path",
    ]

    tfcli = testflinger_cli.TestflingerCli()

    with pytest.raises(SystemExit) as exc_info:
        tfcli.secret_delete()

    assert "Client ID is required for secret operations" in str(exc_info.value)


def test_secret_write_path_with_slashes(auth_fixture, capsys, requests_mock):
    """Test secret write with complex path containing slashes."""
    auth_fixture(ServerRoles.CONTRIBUTOR)
    test_path = "namespace/service/environment/key"
    test_value = "complex_secret_value"

    requests_mock.put(
        f"{URL}/v1/secrets/my_client_id/{test_path}",
        text="OK",
        status_code=HTTPStatus.OK,
    )

    sys.argv = [
        "",
        "secret",
        "write",
        test_path,
        test_value,
    ]

    tfcli = testflinger_cli.TestflingerCli()
    tfcli.secret_write()

    std = capsys.readouterr()
    assert f"Secret '{test_path}' written successfully" in std.out


def test_secret_delete_path_with_slashes(auth_fixture, capsys, requests_mock):
    """Test secret delete with complex path containing slashes."""
    auth_fixture(ServerRoles.CONTRIBUTOR)
    test_path = "namespace/service/environment/key"

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

    tfcli = testflinger_cli.TestflingerCli()
    tfcli.secret_delete()

    std = capsys.readouterr()
    assert f"Secret '{test_path}' deleted successfully" in std.out
