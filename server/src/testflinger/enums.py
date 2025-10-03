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
"""Server Defined Enums."""

from strenum import StrEnum


class ServerRoles(StrEnum):
    """
    Define roles for restricted endpoints and hierarchy among them.

    Implementing a custom "less-than" operator imposes an order between
    the roles (a hierarchy) and allows for comparisons between them.

    The remaining comparison operators are implemented in terms of the
    "less-than" operator.

    Note: functools.total_ordering cannot be used because `StrEnum`
    is first derived from `str` which already provides comparison
    operators. Thus, we need to override them explicitly.
    """

    ADMIN = "admin"
    MANAGER = "manager"
    CONTRIBUTOR = "contributor"
    USER = "user"

    def __lt__(self, other: "ServerRoles") -> bool:
        """Implement of "less-than" between ServerRoles."""
        if not isinstance(other, ServerRoles):
            raise TypeError(
                f"Cannot compare {type(self).__name__} "
                f"to {type(other).__name__}"
            )
        _ranks = {
            self.ADMIN: 0,
            self.MANAGER: 1,
            self.CONTRIBUTOR: 2,
            self.USER: 3,
        }
        return _ranks[self] > _ranks[other]

    def __le__(self, other: "ServerRoles") -> bool:
        """Implement "less-than-or-equal" between ServerRoles."""
        return self < other or self == other

    def __gt__(self, other: "ServerRoles") -> bool:
        """Implement of "greater-than" between ServerRoles."""
        return not (self < other or self == other)

    def __ge__(self, other: "ServerRoles") -> bool:
        """Implement of "greater-than-or-equal" between ServerRoles."""
        return not self < other
