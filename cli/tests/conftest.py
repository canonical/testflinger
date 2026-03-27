# Copyright (C) 2026 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Pytest configuration and shared fixtures for testflinger_cli tests."""

from unittest import mock

import pytest

from testflinger_cli.status_line import StatusLine


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
    StatusLine._is_tty = None
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
def mock_tty():
    """Mock sys.stdout.isatty() to return True."""
    with mock.patch('sys.stdout.isatty', return_value=True):
        yield
