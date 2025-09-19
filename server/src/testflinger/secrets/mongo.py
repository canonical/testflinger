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

"""A Mongo-based implementation for the Testflinger secrets store."""

from pymongo import MongoClient
from pymongo.errors import OperationFailure, ConnectionFailure

from testflinger.secrets.exceptions import AccessError, StoreError
from testflinger.secrets.store import SecretsStore



class MongoStore(SecretsStore):

    def __init__(self, client: MongoClient):
        self.database = client.get_default_database()

    def read(self, namespace: str, key: str) -> str:
        """Return the stored value for `key` under `namespace`."""
        try:
            result = self.database.secrets[namespace].find_one({"key": key})
        except OperationFailure as error:
            raise AccessError(
                f"Unable to access '{key}' under '{namespace}'"
            ) from error
        except ConnectionFailure as error:
            raise StoreError(
                f"Unable to access store for '{key}' under '{namespace}'"
            ) from error
        if result is None:
            raise AccessError(
                f"Unable to access '{key}' under '{namespace}'"
            )
        return result["value"]

    def write(self, namespace: str, key: str, value: str):
        """Write the `value` for `key` under `namespace`."""
        try:
            self.database.secrets[namespace].replace_one(
                {"key": key},
                {"key": key, "value": value},
                upsert=True
            )
        except OperationFailure as error:
            raise AccessError(
                f"Unable to access '{key}' under '{namespace}'"
            ) from error
        except ConnectionFailure as error:
            raise StoreError(
                f"Unable to access store for '{key}' under '{namespace}'"
            ) from error

    def delete(self, namespace: str, key: str):
        """Delete the value for `key` under `namespace`, if any."""
        try:
            self.database.secrets[namespace].delete_one({"key": key})
        except OperationFailure as error:
            raise AccessError(
                f"Unable to access '{key}' under '{namespace}'"
            ) from error
        except ConnectionFailure as error:
            raise StoreError(
                f"Unable to access store for '{key}' under '{namespace}'"
            ) from error
