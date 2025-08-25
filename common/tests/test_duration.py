# Copyright (C) 2025 Canonical
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

"""Tests for duration parsing utilities."""

import pytest
from testflinger_common.duration import parse_duration, DurationParseError


def test_parse_duration_integers():
    """Test parsing integer seconds."""
    assert parse_duration(3600) == 3600
    assert parse_duration("3600") == 3600


def test_parse_duration_formats():
    """Test parsing duration string formats."""
    assert parse_duration("30m") == 1800
    assert parse_duration("5h") == 18000
    assert parse_duration("4d") == 345600
    assert parse_duration("2h30m") == 9000


def test_parse_duration_invalid():
    """Test that invalid formats raise DurationParseError."""
    with pytest.raises(DurationParseError):
        parse_duration("invalid")

    with pytest.raises(DurationParseError):
        parse_duration("-30")
