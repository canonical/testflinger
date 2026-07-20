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

    docker compose exec testflinger python3 devel/create_dev_admin.py

The inserted credential matches the defaults used by create_sample_data.py:
    TESTFLINGER_CLIENT_ID : dev-admin
    TESTFLINGER_SECRET_KEY: dev-secret-for-testing

Sample clients are also inserted with varied client_id/email combinations.
Some emails are intentionally reused across different client IDs to reflect
real-world scenarios where a person owns multiple service accounts.
"""

import os
import sys

import bcrypt
from pymongo import MongoClient

from testflinger.database import get_mongo_uri

DEV_CLIENT_ID = "dev-admin"
DEV_CLIENT_KEY = "dev-secret-for-testing"

# testflinger-admin is the OIDC identity used for authentication via Dex.
# It is registered here so it also has a permissions record in MongoDB.
TESTFLINGER_ADMIN_ID = "testflinger-admin"

# Sample credential-based clients with client_id and email fields.
# alice@example.com is reused across two client IDs to demonstrate that a
# single contact email can be associated with multiple service accounts.
# All other client IDs have unique emails.
SAMPLE_CLIENTS = [
    {
        "client_id": "alice@example.com",
        "email": "alice@example.com",
        "role": "contributor",
        "allowed_queues": [],
        "max_reservation_time": {},
    },
    {
        "client_id": "ci-bot-kernel",
        "email": "alice@example.com",  # same contact as previous
        "role": "contributor",
        "allowed_queues": [],
        "max_reservation_time": {},
    },
    {
        "client_id": "ci-bot-snapd",
        "email": "bob@example.com",
        "role": "contributor",
        "allowed_queues": [],
        "max_reservation_time": {},
    },
    {
        "client_id": "qa-runner-x86",
        "email": "carol@example.com",
        "role": "contributor",
        "allowed_queues": [],
        "max_reservation_time": {},
    },
    {
        "client_id": "infra-agent-arm",
        "email": "dave@example.com",
        "role": "admin",
        "allowed_queues": [],
        "max_reservation_time": {},
    },
]


def _make_secret_hash(secret: str) -> str:
    return bcrypt.hashpw(secret.encode(), bcrypt.gensalt()).decode()


def main():
    mongo_uri = get_mongo_uri()
    mongo_db = os.environ.get("MONGODB_DATABASE", "testflinger_db")
    db = MongoClient(host=mongo_uri)[mongo_db]

    if db.client_permissions.find_one({"client_id": DEV_CLIENT_ID}):
        print(f"Credential '{DEV_CLIENT_ID}' already exists, skipping creation.")
        sys.exit(0)

    secret_hash = _make_secret_hash(DEV_CLIENT_KEY)
    db.client_permissions.insert_one(
        {
            "client_id": DEV_CLIENT_ID,
            "client_secret_hash": secret_hash,
            "role": "admin",
            "max_priority": {"*": 100},
            "allowed_queues": [],
            "max_reservation_time": {},
        }
    )
    print("Created dev admin credential")

    if not db.client_permissions.find_one({"client_id": TESTFLINGER_ADMIN_ID}):
        db.client_permissions.insert_one(
            {
                "client_id": TESTFLINGER_ADMIN_ID,
                "role": "admin",
                "max_priority": {"*": 100},
                "allowed_queues": [],
                "max_reservation_time": {},
            }
        )
        print(f"Created OIDC admin credential '{TESTFLINGER_ADMIN_ID}'")

    for client in SAMPLE_CLIENTS:
        client_id = client["client_id"]
        if db.client_permissions.find_one({"client_id": client_id}):
            print(f"Sample client '{client_id}' already exists, skipping.")
            continue
        doc = {**client, "client_secret_hash": secret_hash}
        db.client_permissions.insert_one(doc)
        print(f"Created sample client '{client_id}' (email: {client['email']})")


if __name__ == "__main__":
    main()
