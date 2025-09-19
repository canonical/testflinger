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
from pymongo.encryption import Algorithm, ClientEncryption
from pymongo.errors import ConnectionFailure, EncryptionError, OperationFailure

from testflinger.secrets.exceptions import AccessError, StoreError
from testflinger.secrets.store import SecretsStore


class MongoStore(SecretsStore):
    """MongoDB-based secrets store using explicit Client-Side Field Level
    Encryption.

    References for Explicit CSFLE (Client-Side Field-Level Encryption):
    https://www.mongodb.com/docs/manual/core/csfle/fundamentals/manual-encryption/
    https://pymongo.readthedocs.io/en/4.13.2/examples/encryption.html#explicit-client-side-encryption
    """

    def __init__(
        self,
        client: MongoClient,
        client_encryption: ClientEncryption,
        data_key_name: str,
    ):
        """Initialize MongoStore with client, encryption, and data key name."""
        self.database = client.get_default_database()
        self.client_encryption = client_encryption
        self.data_key_name = data_key_name
        self.algorithm = Algorithm.AEAD_AES_256_CBC_HMAC_SHA_512_Random

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
            raise AccessError(f"Unable to access '{key}' under '{namespace}'")

        encrypted_value = result["value"]
        try:
            decrypted_value = self.client_encryption.decrypt(encrypted_value)
        except EncryptionError as error:
            raise StoreError(
                f"Failed to decrypt value for '{key}' under '{namespace}'"
            ) from error
        except (UnicodeDecodeError, AttributeError) as error:
            raise StoreError(
                f"Invalid decrypted data format for '{key}' under "
                f"'{namespace}'"
            ) from error

        return decrypted_value.decode("utf-8")

    def write(self, namespace: str, key: str, value: str):
        """Write the `value` for `key` under `namespace`."""
        # Encrypt the value before storing
        try:
            encrypted_value = self.client_encryption.encrypt(
                value=value.encode("utf-8"),
                algorithm=self.algorithm,
                key_alt_name=self.data_key_name,
            )
        except EncryptionError as error:
            raise StoreError(
                f"Failed to encrypt value for '{key}' under '{namespace}'"
            ) from error
        except UnicodeEncodeError as error:
            raise StoreError(
                f"Invalid string format for '{key}' under '{namespace}'"
            ) from error

        try:
            self.database.secrets[namespace].replace_one(
                {"key": key},
                {"key": key, "value": encrypted_value},
                upsert=True,
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
