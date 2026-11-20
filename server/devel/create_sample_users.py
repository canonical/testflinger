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

The inserted credentials match the defaults used by create_sample_data.py:
    TESTFLINGER_ADMIN_ID : testflinger-admin
    TESTFLINGER_AGENT_ID : testflinger-agent

Sample clients are also inserted with varied client_id/email combinations.
Some emails are intentionally reused across different client IDs to reflect
real-world scenarios where a person owns multiple service accounts.
"""

import bcrypt

from testflinger.application import create_flask_app
from testflinger.database import mongo, register_oidc_client
from sample_users import SAMPLE_CLIENTS


def _make_secret_hash(secret: str) -> str:
    return bcrypt.hashpw(secret.encode(), bcrypt.gensalt()).decode()


def main():
    app = create_flask_app()
    with app.app_context():
        db = mongo.db

        deleted = db.client_permissions.delete_many({}).deleted_count
        print(f"Cleared {deleted} client-permissions records.")

        # Create credential and OIDC records independently from known data.
        for client_id, client in SAMPLE_CLIENTS.items():
            if client.get("testflinger_account"):
                credential_id = client["client_id"]
                credential = db.client_permissions.find_one(
                    {"client_id": credential_id}
                )
                if credential is None:
                    secret_key = client["secret_key"]
                    credential_doc = {
                        key: value
                        for key, value in client.items()
                        if key not in {
                            "testflinger_account",
                            "dex_account",
                            "dev_auto_signin",
                            "sub",
                            "secret_key",
                        }
                    }
                    credential_doc["client_secret_hash"] = _make_secret_hash(
                        secret_key
                    )
                    db.client_permissions.insert_one(credential_doc)
                    print(f"Created credential client '{credential_id}'.")
                elif credential.get("sub"):
                    # Older samples put the Dex subject on the credential row.
                    db.client_permissions.update_one(
                        {"_id": credential["_id"]},
                        {"$unset": {"sub": ""}},
                    )
                    print(
                        "Removed Dex subject from credential "
                        f"'{credential_id}'."
                    )

            if not client.get("dex_account"):
                continue

            # Same upsert as a real login, then apply the sample role.
            register_oidc_client(
                {
                    "sub": client["sub"],
                    "email": client["email"],
                    "name": client.get("name", ""),
                }
            )
            db.client_permissions.update_one(
                {"sub": client["sub"]}, {"$set": {"role": client["role"]}}
            )
            print(f"Upserted Dex account for subject '{client['sub']}'.")


if __name__ == "__main__":
    main()
