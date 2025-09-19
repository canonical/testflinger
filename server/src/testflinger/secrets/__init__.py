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
import os

import pymongo.errors
from bson.binary import STANDARD, Binary
from bson.codec_options import CodecOptions
from hvac import Client
from pymongo import MongoClient
from pymongo.encryption import ClientEncryption
from pymongo.errors import EncryptionError

from testflinger.database import get_mongo_uri
from testflinger.secrets.exceptions import StoreError
from testflinger.secrets.mongo import MongoStore
from testflinger.secrets.store import SecretsStore
from testflinger.secrets.vault import VaultStore


def setup_vault_store() -> VaultStore | None:
    vault_url = os.environ.get("TESTFLINGER_VAULT_URL")
    vault_token = os.environ.get("TESTFLINGER_VAULT_TOKEN")
    if not vault_url or not vault_token:
        return None

    client = Client(url=vault_url, token=vault_token)
    if not client.is_authenticated():
        raise StoreError("Vault client not authenticated")

    return VaultStore(client)


def setup_mongo_store() -> MongoStore | None:
    mongo_url = get_mongo_uri()

    # Get master key from environment
    master_key_b64 = os.environ.get("MONGO_MASTER_KEY")

    if not master_key_b64:
        raise StoreError("MONGO_MASTER_KEY environment variable not set")

    try:
        master_key = base64.b64decode(master_key_b64)
    except Exception as error:
        raise StoreError("Invalid MONGO_MASTER_KEY format") from error

    # Create regular client without auto-encryption for explicit CSFLE
    # Reference: https://www.mongodb.com/docs/manual/core/csfle/fundamentals/manual-encryption/
    # PyMongo docs: https://pymongo.readthedocs.io/en/stable/examples/encryption.html#explicit-encryption-and-decryption
    client = MongoClient(mongo_url)

    # Set up key vault and client encryption for explicit encryption
    kms_providers = {"local": {"key": master_key}}
    key_vault_db = "encryption"
    key_vault_collection = "__keyVault"
    key_alt_name = "testflinger-secrets"

    client = MongoClient(mongo_url)

    client_encryption = ClientEncryption(
        kms_providers=kms_providers,
        key_vault_namespace=f"{key_vault_db}.{key_vault_collection}",
        key_vault_client=client,
        codec_options=CodecOptions(),
    )

    key_vault = client[key_vault_db][key_vault_collection]

    existing_key = key_vault.find_one({"keyAltNames": key_alt_name})
    if not existing_key:
        try:
            client_encryption.create_data_key(
                "local", key_alt_names=[key_alt_name]
            )
        except EncryptionError as error:
            raise StoreError(
                f"Failed to create data encryption key: {error}"
            ) from error

    """
    try:
        client.admin.command('ping')
    except pymongo.errors.ConnectionFailure as error:
         raise StoreError(
            f"Mongo client unable to ping database at {mongo_url}"
         ) from error
    """

    client_encryption.rewrap_many_data_key(
        filter={"keyAltNames": [key_alt_name]}
    )
    print(client_encryption, client_encryption.__dict__)
    return MongoStore(client, client_encryption, key_alt_name)


def setup_secrets_store() -> SecretsStore | None:
    """
    Create and return a store for secrets, if possible.

    Currently, the store returned is an instance of `VaultStore`.

    Not setting up a secrets store is not an error: it just means that
    Testflinger jobs will not be able to use secrets.
    """
    # return setup_vault_store()
    return setup_mongo_store()
