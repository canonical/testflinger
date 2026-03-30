# Copyright (C) 2026 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Shared pytest fixtures and configuration."""

import uuid

import jwt
import pytest

from testflinger_cli.status_line import StatusLine

from .test_cli import URL

# Mock required authentication
TEST_CLIENT_ID = "my_client_id"
TEST_SECRET_KEY = "my_secret_key"
JWT_SIGNING_KEY = "my-secret"


@pytest.fixture(autouse=True)
def mock_xdg_config(monkeypatch, tmp_path):
    """Mock XDG config home for all tests to ensure isolation.

    This prevents tests from accessing refresh token storage location
    and ensures each test has a clean, isolated environment.
    """
    # Mock the xdg_config_home function to return tmp path
    monkeypatch.setattr(
        "testflinger_cli.auth.xdg_config_home", lambda: tmp_path
    )


@pytest.fixture
def auth_fixture(monkeypatch, requests_mock):
    """Configure fixture for test that require authentication."""

    def _fixture(role):
        monkeypatch.setenv("TESTFLINGER_CLIENT_ID", TEST_CLIENT_ID)
        monkeypatch.setenv("TESTFLINGER_SECRET_KEY", TEST_SECRET_KEY)

        fake_payload = {
            "permissions": {"client_id": TEST_CLIENT_ID, "role": role}
        }
        fake_jwt_token = jwt.encode(
            fake_payload, JWT_SIGNING_KEY, algorithm="HS256"
        )
        fake_return = {
            "access_token": fake_jwt_token,
            "token_type": "Bearer",
            "expires_in": 30,
            "refresh_token": str(uuid.uuid4()),
        }
        requests_mock.post(f"{URL}/v1/oauth2/token", json=fake_return)

    return _fixture


@pytest.fixture(autouse=True)
def reset_status_line():
    """Reset StatusLine state before and after each test."""
    # Reset before test
    StatusLine._running = False
    StatusLine._timer_thread = None
    StatusLine._original_start_time = None
    StatusLine._start_time = None
    StatusLine._countdown_mode = False
    StatusLine._countdown_start_value = 0
    StatusLine._is_tty = False
    StatusLine.message = ""
    StatusLine.state = ""
    StatusLine._prev_state = None
    StatusLine._state_start_time = None
    StatusLine._last_template = ""

    yield

    # Cleanup after test
    if StatusLine._running:
        StatusLine.stop()


@pytest.fixture
def mock_tty(monkeypatch):
    """Mock sys.stdout.isatty() to return True before StatusLine.init() is
     called.

    This fixture must be used BEFORE StatusLine.init() is called in the test.
    It patches sys.stdout.isatty() at the module level so StatusLine.init()
    will see the mocked return value.
    """
    monkeypatch.setattr(
        "testflinger_cli.status_line.sys.stdout.isatty", lambda: True
    )
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    yield
