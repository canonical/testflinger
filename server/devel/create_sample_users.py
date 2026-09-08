#!/usr/bin/env python3
# Copyright (C) 2026 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
Populate local development MongoDB with a well-known admin client credential
and a set of sample credential-based clients with client_id and email fields.

This lets create_sample_data.py work against an authenticated server without
having to configure credentials manually. This needs to run in the testflinger
container.

    docker compose exec testflinger python3 devel/create_sample_users.py

The inserted credential matches the defaults used by create_sample_data.py:
    TESTFLINGER_CLIENT_ID : testflinger-admin
    TESTFLINGER_SECRET_KEY: testflinger

Sample clients are also inserted with varied client_id/email combinations.
Some emails are intentionally reused across different client IDs to reflect
real-world scenarios where a person owns multiple service accounts.
"""

import os

import bcrypt
from pymongo import MongoClient

from testflinger.database import get_mongo_uri
from sample_users import (
    SAMPLE_CLIENTS,
    TESTFLINGER_ADMIN,
)

# testflinger-admin is both the OIDC identity (via Dex) and a credential-based
# admin client used by create_sample_data.py.


def _make_secret_hash(secret: str) -> str:
    return bcrypt.hashpw(secret.encode(), bcrypt.gensalt()).decode()


def main():
    mongo_uri = get_mongo_uri()
    mongo_db = os.environ.get("MONGODB_DATABASE", "testflinger_db")
    db = MongoClient(host=mongo_uri)[mongo_db]

    admin_client_id = TESTFLINGER_ADMIN["client_id"]
    if not db.client_permissions.find_one({"client_id": admin_client_id}):
        admin_doc = {**TESTFLINGER_ADMIN}
        admin_doc["client_secret_hash"] = _make_secret_hash(
            admin_doc.pop("secret_key")
        )
        db.client_permissions.insert_one(admin_doc)
        print(f"Created admin credential '{admin_client_id}'")

    for client in SAMPLE_CLIENTS:
        client_id = client["client_id"]
        if db.client_permissions.find_one({"client_id": client_id}):
            print(f"Sample client '{client_id}' already exists, skipping.")
            continue
        secret_key = client["secret_key"]
        doc = {**client, "client_secret_hash": _make_secret_hash(secret_key)}
        db.client_permissions.insert_one(doc)
        print(
            f"Created sample client '{client_id}' (email: {client['email']})"
        )


if __name__ == "__main__":
    main()
