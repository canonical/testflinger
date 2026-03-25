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

"""Default setup for the Testflinger secrets store."""

import base64
import binascii
import logging
import os
from contextlib import suppress

import requests
from bson.codec_options import CodecOptions
from hvac import Client
from pymongo import MongoClient
from pymongo.encryption import ClientEncryption
from pymongo.errors import DuplicateKeyError, EncryptionError, PyMongoError

from testflinger.database import get_mongo_uri
from testflinger.secrets.exceptions import StoreError
from testflinger.secrets.mongo import MongoStore
from testflinger.secrets.store import SecretsStore
from testflinger.secrets.vault import VaultStore

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter(
    "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S %z",
)
handler.setFormatter(formatter)
logger.addHandler(handler)

KEY_VAULT_DATABASE = "encryption"
KEY_VAULT_COLLECTION = "__keyVault"


def setup_vault_store() -> VaultStore:
    """
    Set up HashiCorp Vault-based secrets store.

    Creates a VaultStore instance using environment variables for
    configuration.

    Returns:
        A VaultStore, if the appropriate environment variables have been set
        or None otherwise.

    Raises:
        StoreError: If Vault client authentication fails
    """
    vault_url = os.environ.get("TESTFLINGER_VAULT_URL")
    vault_token = os.environ.get("TESTFLINGER_VAULT_TOKEN")
    if not vault_url or not vault_token:
        return None

    client = Client(url=vault_url, token=vault_token)
    try:
        if not client.is_authenticated():
            raise StoreError("Vault client not authenticated")
    except requests.exceptions.ConnectionError as error:
        raise StoreError("Vault client unable to connect") from error

    return VaultStore(client)


def _decode_master_key(b64_key: str) -> bytes:
    """Decode a base64-encoded master key.

    :param b64_key: Base64-encoded master key string.
    :return: Raw key bytes.
    :raises StoreError: If string is not valid base64 or incorrect length.
    """
    try:
        key_bytes = base64.b64decode(b64_key, validate=True)
    except (binascii.Error, ValueError) as error:
        raise StoreError(
            "Invalid TESTFLINGER_SECRETS_MASTER_KEY: value is not valid base64"
        ) from error
    if len(key_bytes) != 96:
        raise StoreError(
            "Invalid TESTFLINGER_SECRETS_MASTER_KEY: "
            "decoded key must be 96 bytes for MongoDB local KMS"
        )
    return key_bytes


def _make_cipher(
    key_vault_client: MongoClient,
    master_key: bytes,
    key_vault_namespace: str,
    kms_providers: dict | None = None,
) -> ClientEncryption:
    """Create a ClientEncryption instance for the given master key.

    :param key_vault_client: MongoClient with access to the key vault database.
    :param master_key: Raw master key bytes.
    :param key_vault_namespace: Fully-qualified key vault namespace.
    :param kms_providers: Optional KMS providers map.
    """
    return ClientEncryption(
        kms_providers=kms_providers or {"local": {"key": master_key}},
        key_vault_namespace=key_vault_namespace,
        key_vault_client=key_vault_client,
        codec_options=CodecOptions(),
    )


def setup_mongo_store() -> MongoStore | None:
    """
    Set up MongoDB-based secrets store with Client-Side Field Level Encryption.

    Creates a MongoStore instance using explicit CSFLE for secret storage.
    The function handles data encryption key creation/rotation.

    Returns:
        A MongoStore, if the appropriate environment variables have been set
        or None otherwise.

    Raises:
        StoreError: If master key is missing/invalid or encryption setup fails
    """
    try:
        mongo_url = get_mongo_uri()
    except SystemExit:
        return None

    master_key_b64 = os.environ.get("TESTFLINGER_SECRETS_MASTER_KEY")
    if not master_key_b64:
        return None

    master_key = _decode_master_key(master_key_b64)

    # Explicit Client-Side Field-Level Encryption
    # Reference: https://www.mongodb.com/docs/manual/core/csfle/fundamentals/manual-encryption/
    # PyMongo docs: https://pymongo.readthedocs.io/en/stable/examples/encryption.html#explicit-encryption-and-decryption
    client = MongoClient(mongo_url)

    # Production instance should use a dedicated client for the key vault.
    # For dev testing, reuse the same MongoClient instance if URI not provided.
    key_vault_uri = os.environ.get("TESTFLINGER_KEY_VAULT_URI")
    key_vault_client = MongoClient(key_vault_uri) if key_vault_uri else client

    # human-readable name for the data key that encrypts the secrets
    key_name = "testflinger-secrets"
    # all encryption/decryption of secret values goes through the cipher
    # (i.e. a `ClientEncryption` object)
    cipher = _make_cipher(
        key_vault_client=key_vault_client,
        master_key=master_key,
        key_vault_namespace=f"{KEY_VAULT_DATABASE}.{KEY_VAULT_COLLECTION}",
    )

    # Ensure the unique partial index on keyAltNames exists so that concurrent
    # units cannot create duplicate DEKs for the same key_name.
    key_vault = key_vault_client[KEY_VAULT_DATABASE][KEY_VAULT_COLLECTION]
    try:
        key_vault.create_index(
            "keyAltNames",
            unique=True,
            partialFilterExpression={"keyAltNames": {"$exists": True}},
        )

        # create data encryption key, if none exists
        existing_key = key_vault.find_one({"keyAltNames": key_name})
        if not existing_key:
            try:
                cipher.create_data_key("local", key_alt_names=[key_name])
            except DuplicateKeyError:
                # A concurrent unit won the race and already created the DEK.
                pass
            except EncryptionError as error:
                raise StoreError(
                    f"Failed to create data encryption key: {error}"
                ) from error
    except PyMongoError as error:
        raise StoreError(
            f"Failed to access the key vault collection: {error}"
        ) from error

    return MongoStore(client, cipher, key_name)


def setup_secrets_store() -> SecretsStore | None:
    """
    Create and return a store for secrets, if possible.

    Currently, the store returned is an instance of `VaultStore`.

    Not setting up a secrets store is not an error: it just means that
    Testflinger jobs will not be able to use secrets.
    """
    with suppress(StoreError):
        store = setup_vault_store()
        if store is not None:
            logger.info(
                "Successfully initialized the secrets store (Vault-based)"
            )
            return store

    with suppress(StoreError):
        store = setup_mongo_store()
        if store is not None:
            logger.info(
                "Successfully initialized the secrets store (Mongo-based)"
            )
            return store

    logger.warning("The secrets store has not been initialized")
