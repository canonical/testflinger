# Copyright (C) 2025 Canonical Ltd.
"""Shared pytest fixtures and configuration."""

import builtins
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
def cleanup_statusline():
    """Cleanup StatusLine after each test to prevent state pollution."""
    # Reset before test
    StatusLine._running = False
    StatusLine._timer_thread = None
    StatusLine.message = ""
    StatusLine.state = ""
    StatusLine._is_tty = None
    StatusLine._start_time = None
    StatusLine._last_printed_message = ""
    StatusLine._countdown_mode = False
    StatusLine._prev_state = None
    StatusLine._state_start_time = None

    yield

    # Cleanup after test
    StatusLine.stop()
    # Ensure builtins are restored to original state
    from testflinger_cli.status_line import _original_input, _original_print

    builtins.print = _original_print
    builtins.input = _original_input
    # Reset StatusLine state for next test
    StatusLine._running = False
    StatusLine._timer_thread = None
    StatusLine.message = ""
    StatusLine.state = ""
    StatusLine._is_tty = None
    StatusLine._start_time = None
    StatusLine._last_printed_message = ""
    StatusLine._countdown_mode = False
    StatusLine._prev_state = None
    StatusLine._state_start_time = None


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
