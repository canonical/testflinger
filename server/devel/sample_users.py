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
Sample user data for use in local testing and development.
"""

# This is the single handwritten source for local accounts. Entries with a
# dex_user_id are rendered into dex-config.yaml. Entries with dev_auto_signin
# are also rendered into testflinger.dev_signin_identities.
SAMPLE_CLIENTS = [
    {
        "client_id": "testflinger-admin",
        "email": "testflinger@example.com",
        "name": "testflinger-admin",
        "dex_user_id": "1001",
        "dev_auto_signin": True,
        "role": "admin",
        "max_priority": {"*": 100},
        "allowed_queues": [],
        "max_reservation_time": {},
        "secret_key": "testflinger",  # noqa: S105
    },
    {
        "client_id": "alice-sample-client",
        "email": "alice@example.com",
        "name": "alice",
        "dex_user_id": "1003",
        "dev_auto_signin": True,
        "role": "admin",
        "allowed_queues": [],
        "max_reservation_time": {},
        "secret_key": "testflinger",
    },
    {
        "client_id": "ci-bot-kernel",
        "email": "alice@example.com",
        "role": "contributor",
        "allowed_queues": [],
        "max_reservation_time": {},
        "secret_key": "testflinger",
    },
    {
        "client_id": "ci-bot-snapd",
        "email": "bob@example.com",
        "name": "bob",
        "dex_user_id": "1004",
        "dev_auto_signin": True,
        "role": "manager",
        "allowed_queues": [],
        "max_reservation_time": {},
        "secret_key": "testflinger",
    },
    {
        "client_id": "qa-runner-x86",
        "email": "carol@example.com",
        "name": "carol",
        "dex_user_id": "1005",
        "dev_auto_signin": True,
        "role": "contributor",
        "allowed_queues": [],
        "max_reservation_time": {},
        "secret_key": "testflinger",
    },
    {
        "client_id": "infra-agent-arm",
        "email": "dave@example.com",
        "role": "contributor",
        "allowed_queues": [],
        "max_reservation_time": {},
        "secret_key": "testflinger",
    },
]

# Existing callers use these defaults to create sample data.
TESTFLINGER_ADMIN = next(
    client
    for client in SAMPLE_CLIENTS
    if client["client_id"] == "testflinger-admin"
)
TESTFLINGER_ADMIN_ID = TESTFLINGER_ADMIN["client_id"]
TESTFLINGER_ADMIN_SECRET = TESTFLINGER_ADMIN["secret_key"]
