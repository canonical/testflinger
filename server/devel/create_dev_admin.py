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
Populate local development MongoDB with a well-known admin client credential.

This lets create_sample_data.py work against an authenticated server without
having to configure credentials manually. This needs to run in the testflinger
container.

    docker compose exec testflinger python3 devel/create_dev_admin.py

The inserted credential matches the defaults used by create_sample_data.py:
    TESTFLINGER_CLIENT_ID : dev-admin
    TESTFLINGER_SECRET_KEY: dev-secret-for-testing
"""

import os
import sys

import bcrypt
from pymongo import MongoClient

from testflinger.database import get_mongo_uri

DEV_CLIENT_ID = "dev-admin"
DEV_CLIENT_KEY = "dev-secret-for-testing"


def main():
    mongo_uri = get_mongo_uri()
    mongo_db = os.environ.get("MONGODB_DATABASE", "testflinger_db")
    db = MongoClient(host=mongo_uri)[mongo_db]

    if db.client_permissions.find_one({"client_id": DEV_CLIENT_ID}):
        print(f"Credential '{DEV_CLIENT_ID}' already exists, skipping creation.")
        sys.exit(0)

    secret_hash = bcrypt.hashpw(
        DEV_CLIENT_KEY.encode(), bcrypt.gensalt()
    ).decode()
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


if __name__ == "__main__":
    main()
