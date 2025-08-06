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

"""Tests for duration field in server schemas."""

import pytest
from marshmallow import ValidationError

from testflinger.api.schemas import DurationField, ReserveData


def test_duration_field_integers():
    """Test DurationField with integer seconds."""
    field = DurationField()
    assert field.deserialize(3600) == 3600
    assert field.deserialize("3600") == 3600


def test_duration_field_formats():
    """Test DurationField with duration string formats."""
    field = DurationField()
    assert field.deserialize("30m") == 1800
    assert field.deserialize("2h30m") == 9000


def test_duration_field_invalid():
    """Test DurationField with invalid formats."""
    field = DurationField()
    with pytest.raises(ValidationError):
        field.deserialize("invalid")


def test_reserve_data_schema():
    """Test ReserveData schema with duration timeout."""
    schema = ReserveData()
    data = {"ssh_keys": ["lp:user"], "timeout": "2h30m"}
    result = schema.load(data)
    assert result["timeout"] == 9000
