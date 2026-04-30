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

from datetime import datetime, timedelta, timezone

from pymongo import MongoClient
from pymongo.encryption import Algorithm, ClientEncryption
from pymongo.errors import ConnectionFailure, EncryptionError, OperationFailure

from testflinger.secrets.exceptions import AccessError, StoreError
from testflinger.secrets.store import DEFAULT_SECRET_EXPIRATION, SecretsStore


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
        cipher: ClientEncryption,
        data_key_name: str,
        algorithm: Algorithm = Algorithm.AEAD_AES_256_CBC_HMAC_SHA_512_Random,
    ):
        """Initialize MongoStore with client, cipher, data key name and
        (optionally) the algorithm used for encryption.
        """
        self.database = client.get_default_database()
        self.cipher = cipher
        self.data_key_name = data_key_name
        self.algorithm = algorithm
        self._ttl_index_initialized_namespaces = set()

    def _ensure_ttl_index(self, namespace: str):
        """Create the TTL index for a namespace collection, if needed."""
        if namespace in self._ttl_index_initialized_namespaces:
            return

        try:
            self.database.secrets[namespace].create_index(
                "expire_at", expireAfterSeconds=0
            )
        except OperationFailure as error:
            raise AccessError(
                f"Unable to access '{namespace}' namespace"
            ) from error
        except ConnectionFailure as error:
            raise StoreError(
                f"Unable to access store for '{namespace}' namespace"
            ) from error

        self._ttl_index_initialized_namespaces.add(namespace)

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

        # Deny access to expired secrets while waiting for MongoDB TTL cleanup
        expire_at = result.get("expire_at")
        if expire_at is not None and expire_at.replace(
            tzinfo=timezone.utc
        ) < datetime.now(timezone.utc):
            raise AccessError(f"Expired '{key}' under '{namespace}'")

        try:
            decrypted_value = self.cipher.decrypt(encrypted_value)
        except EncryptionError as error:
            raise StoreError(
                f"Failed to decrypt value for '{key}' under '{namespace}'"
            ) from error
        if decrypted_value is None:
            raise StoreError(
                f"Failed to decrypt value for '{key}' under '{namespace}'"
            )

        # If secret is ephemeral, delete it after reading
        if result.get("ephemeral", False):
            self.delete(namespace, key)

        # Return the decrypted value as a UTF-8 string, if possible
        try:
            return decrypted_value.decode("utf-8")
        except UnicodeDecodeError as error:
            raise StoreError(
                f"Failed to decrypt value for '{key}' under '{namespace}'"
            ) from error

    def write(
        self,
        namespace: str,
        key: str,
        value: str,
        expire_after: int | None = DEFAULT_SECRET_EXPIRATION,
        ephemeral: bool = False,
    ) -> datetime | None:
        """Write the `value` for `key` under `namespace`.

        Secret TTL is defined by `expire_after` in seconds or `ephemeral`
        with a mutual exclusion guaranteed by schema.

        :param namespace: the namespace under which to store the secret
        :param key: the key for the secret
        :param value: the value of the secret to store
        :param expire_after: Expiration time in seconds for the secret.
        :param ephemeral: whether the secret should be deleted after being read
        :returns: The expiry datetime if a TTL was set, otherwise None.
        :raises AccessError: if the secret cannot be accessed
        :raises StoreError: if there is an issue with the MongoDB store
        """
        try:
            encrypted_value = self.cipher.encrypt(
                value=value.encode("utf-8"),
                algorithm=self.algorithm,
                key_alt_name=self.data_key_name,
            )
        except (EncryptionError, UnicodeEncodeError) as error:
            raise StoreError(
                f"Failed to encrypt value for '{key}' under '{namespace}'"
            ) from error

        secret_document = {
            "key": key,
            "value": encrypted_value,
            "updated_at": datetime.now(timezone.utc),
            "ephemeral": ephemeral,
        }
        # Only add expiration and create TTL index if secret is not ephemeral
        # and has an expiration defined
        expire_at = None
        if not ephemeral and expire_after is not None:
            self._ensure_ttl_index(namespace)
            expire_at = datetime.now(timezone.utc) + timedelta(
                seconds=expire_after
            )
            secret_document["expire_at"] = expire_at

        try:
            self.database.secrets[namespace].replace_one(
                {"key": key},
                secret_document,
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

        return expire_at

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

    def exists(self, namespace: str, key: str) -> bool:
        """Check if the `key` exists under `namespace`.

        :param namespace: The namespace to check for the secret.
        :param key: The key for the secret to check.
        :returns: True if the secret exists, False otherwise.
        """
        try:
            return (
                self.database.secrets[namespace].find_one(
                    {
                        "key": key,
                        "$or": [
                            {"expire_at": {"$exists": False}},
                            {"expire_at": {"$gt": datetime.now(timezone.utc)}},
                        ],
                    },
                    {"_id": 1},
                )
                is not None
            )
        except (OperationFailure, ConnectionFailure):
            return False
