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

"""Tool for rotating the MongoDB secrets master key.

Re-wraps all DEKs in __keyVault under a new master key using
rewrap_many_data_key. Secret values are not touched. Triggered automatically
by the charm when testflinger_secrets_master_key config changes.

Environment variables:
  TESTFLINGER_SECRETS_MASTER_KEY      current master key (base64, required)
  TESTFLINGER_SECRETS_NEW_MASTER_KEY  new master key (base64, required)
  TESTFLINGER_KEY_VAULT_URI           key vault MongoDB URI (optional);
                                      falls back to MONGODB_* when unset
  MONGODB_*                           standard MongoDB connection variables
"""

import os
import sys

from pymongo import MongoClient

from testflinger.database import get_mongo_uri
from testflinger.secrets import (
    KEY_VAULT_COLLECTION,
    KEY_VAULT_DATABASE,
    _decode_master_key,
    _make_cipher,
)


def rotate_master_key(
    old_master_key: bytes,
    new_master_key: bytes,
    key_vault_ns: str,
    key_vault_uri: str,
) -> None:
    """Re-wrap all DEKs in __keyVault under a new master key.

    :param old_master_key: Current master key bytes.
    :param new_master_key: New master key bytes.
    :param key_vault_ns: Namespace of the key vault collection
    :param key_vault_uri: URI for the key vault database.
    """
    key_vault_client = MongoClient(key_vault_uri)
    print("Re-wrapping DEK(s) under new master key...")

    try:
        # Create cipher with old and new master keys as separate KMS providers.
        # Required as rewrap_many_data_key does not support passing
        # master_key directly to "local" KMS provider.
        cipher = _make_cipher(
            key_vault_client,
            old_master_key,
            key_vault_ns,
            kms_providers={
                "local": {"key": old_master_key},
                "local:new": {"key": new_master_key},
            },
        )
        try:
            result = cipher.rewrap_many_data_key({}, provider="local:new")
            count = (
                result.bulk_write_result.modified_count
                if result.bulk_write_result
                else 0
            )
        finally:
            cipher.close()
        # Set the new master key in "local" provider and rewrap back to "local"
        cipher = _make_cipher(
            key_vault_client,
            new_master_key,
            key_vault_ns,
            kms_providers={
                "local:new": {"key": new_master_key},
                "local": {"key": new_master_key},
            },
        )
        try:
            cipher.rewrap_many_data_key({}, provider="local")
        finally:
            cipher.close()
        print(f"Re-wrapped {count} DEK(s).")
        print("Rotation complete.")
    finally:
        key_vault_client.close()


def main() -> None:
    """Entry point for the rotate_mongo_secrets_key script."""
    old_b64 = os.environ.get("TESTFLINGER_SECRETS_MASTER_KEY")
    new_b64 = os.environ.get("TESTFLINGER_SECRETS_NEW_MASTER_KEY")

    if not old_b64 or not new_b64:
        print(
            "Error: both TESTFLINGER_SECRETS_MASTER_KEY and "
            "TESTFLINGER_SECRETS_NEW_MASTER_KEY are required.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Production should use a separate URI for the key vault
    # Dev testing can build the URI from the MONGODB_* env vars
    mongo_uri = os.environ.get("TESTFLINGER_KEY_VAULT_URI") or get_mongo_uri()

    rotate_master_key(
        old_master_key=_decode_master_key(old_b64),
        new_master_key=_decode_master_key(new_b64),
        key_vault_ns=f"{KEY_VAULT_DATABASE}.{KEY_VAULT_COLLECTION}",
        key_vault_uri=mongo_uri,
    )


if __name__ == "__main__":
    main()
