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
"""Unit tests for Testflinger enums."""

from itertools import pairwise

import pytest

from testflinger.enums import ServerRoles


@pytest.fixture
def sorted_roles():
    """Return sorted list of ServerRoles."""
    return sorted(ServerRoles)


class TestServerRoles:
    """Test ServerRoles enum."""

    def test_compare_with_next(self, sorted_roles):
        """Test consecutive pairs of roles."""
        for lower, higher in pairwise(sorted_roles):
            assert lower < higher
            assert not (lower >= higher)
            assert lower <= higher
            assert not (lower > higher)
            assert higher > lower
            assert not (higher <= lower)
            assert higher >= lower
            assert not (higher < lower)

    def test_compare_with_self(self, sorted_roles):
        """Test with same role."""
        for role in sorted_roles:
            assert role == role
            assert role <= role
            assert role >= role
            assert not (role != role)
            assert not (role < role)
            assert not (role > role)

    def test_comparison_type_error(self):
        """Test that comparing with non-ServerRoles raises TypeError."""
        with pytest.raises(
            TypeError, match="Cannot compare ServerRoles to str"
        ):
            ServerRoles.ADMIN < "admin"  # noqa: B015

        with pytest.raises(
            TypeError, match="Cannot compare ServerRoles to int"
        ):
            ServerRoles.ADMIN < 1  # noqa: B015

        with pytest.raises(
            TypeError, match="Cannot compare ServerRoles to NoneType"
        ):
            ServerRoles.ADMIN < None  # noqa: B015

    def test_role_ordering(self, sorted_roles):
        """Test that roles are ordered correctly."""
        unsorted_roles = list(reversed(sorted_roles))
        assert sorted(unsorted_roles) == sorted_roles
