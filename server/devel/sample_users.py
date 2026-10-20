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

# Note this list of users is used both here and in create_sample_users. It is
# located in this file due to import and execution environments with respect
# to mongodb. While create_sample_users can import this file, the other
# direction is not possible.

# Known account IDs for special clients
TESTFLINGER_ADMIN_ID = "testflinger-admin"
TESTFLINGER_AGENT_ID = "testflinger-agent"

# This is the single handwritten source for local accounts. Entries with a
# dex_user_id are rendered into dex-config.yaml. Entries with dev_auto_signin
# are also rendered into testflinger.dev_signin_identities.
SAMPLE_CLIENTS = {
    TESTFLINGER_ADMIN_ID: {
        "client_id": TESTFLINGER_ADMIN_ID,
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
    "alice-sample-client": {
        "client_id": "alice-sample-client",
        "email": "alice@example.com",
        "name": "alice",
        "dex_user_id": "1003",
        "dev_auto_signin": True,
        "role": "admin",
        "allowed_queues": [],
        "max_reservation_time": {},
        "secret_key": "testflinger",  # noqa: S105
    },
    TESTFLINGER_AGENT_ID: {
        "client_id": TESTFLINGER_AGENT_ID,
        "email": "testflinger-agent@example.com",
        "name": "testflinger-agent",
        "role": "agent",
        "allowed_queues": [],
        "max_reservation_time": {},
        "secret_key": "testflinger",  # noqa: S105
    },
    "ci-bot-kernel": {
        "client_id": "ci-bot-kernel",
        "email": "alice@example.com",
        "role": "contributor",
        "allowed_queues": [],
        "max_reservation_time": {},
        "secret_key": "testflinger",  # noqa: S105
    },
    "ci-bot-snapd": {
        "client_id": "ci-bot-snapd",
        "email": "bob@example.com",
        "name": "bob",
        "dex_user_id": "1004",
        "dev_auto_signin": True,
        "role": "manager",
        "allowed_queues": [],
        "max_reservation_time": {},
        "secret_key": "testflinger",  # noqa: S105
    },
    "qa-runner-x86": {
        "client_id": "qa-runner-x86",
        "email": "carol@example.com",
        "name": "carol",
        "dex_user_id": "1005",
        "dev_auto_signin": True,
        "role": "contributor",
        "allowed_queues": [],
        "max_reservation_time": {},
        "secret_key": "testflinger",  # noqa: S105
    },
    "infra-agent-arm": {
        "client_id": "infra-agent-arm",
        "email": "dave@example.com",
        "role": "contributor",
        "allowed_queues": [],
        "max_reservation_time": {},
        "secret_key": "testflinger",  # noqa: S105
    },
}
