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

"""Abstract base class defining the interface to the secrets store."""

from abc import ABC, abstractmethod


class SecretsStore(ABC):
    """
    Classes derived from this abstract base class implement the interface
    for a secrets store, i.e. an entity that can securely read, write and
    delete key-value pairs under different namespaces.

    All class methods are expected to raise an appropriate instance of
    testflinger.secrets.exceptions.SecretsError if they encounter an issue.
    """

    @abstractmethod
    def read(self, namespace: str, key: str) -> str:
        """Return the stored value for `key` under `namespace`."""
        raise NotImplementedError

    @abstractmethod
    def is_accessible(self, namespace: str, key: str) -> bool:
        """Check if there is a stored value for `key` under `namespace`."""
        raise NotImplementedError

    @abstractmethod
    def write(self, namespace: str, key: str, value: str):
        """Write the `value` for `key` under `namespace`."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, namespace: str, key: str):
        """Delete the value for `key` under `namespace`, if any."""
        raise NotImplementedError
