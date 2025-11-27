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

"""
Exceptions related to the Testflinger secrets store.

Ref: https://python-hvac.org/en/stable/source/hvac_exceptions.html#module-hvac.exceptions
"""


class SecretsError(Exception):
    """Base class for errors related to the secrets store."""

    pass


class AccessError(SecretsError):
    """
    Raised if the secrets store can be reached but a specific secret
    cannot be accessed. For security reasons, an access error deliberately
    makes no distinction between e.g. key errors (a secret does not exist)
    and permission errors (a secret exists but access is not authorized).
    """

    pass


class StoreError(SecretsError):
    """Raised when there is an issue communicating with the secrets store."""

    pass


class UnexpectedError(SecretsError):
    """
    Catch-all class for secrets store errors not appropriate for the other
    secrets store exceptions.
    """

    pass
