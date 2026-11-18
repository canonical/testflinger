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
"""Sample account data for local development and integration testing.

Each entry independently enables a Testflinger credential account and a Dex
OIDC account. The credential and Dex accounts are separate Mongo records and
may share an email address.
"""

TESTFLINGER_ADMIN_ID = "testflinger-admin"
TESTFLINGER_AGENT_ID = "testflinger-agent"

SAMPLE_CLIENTS = {
    TESTFLINGER_ADMIN_ID: {
        "testflinger_account": True,
        "dex_account": True,
        "client_id": TESTFLINGER_ADMIN_ID,
        "email": "testflinger@example.com",
        "name": "testflinger-admin",
        "sub": "1001",
        "role": "admin",
        "max_priority": {"*": 100},
        "allowed_queues": [],
        "max_reservation_time": {},
        "secret_key": "testflinger",  # noqa: S105
    },
    "alice-sample-client": {
        "testflinger_account": True,
        "dex_account": True,
        "client_id": "alice-sample-client",
        "email": "alice@example.com",
        "name": "alice",
        "sub": "1003",
        "role": "admin",
        "allowed_queues": [],
        "max_reservation_time": {},
        "secret_key": "testflinger",  # noqa: S105
    },
    TESTFLINGER_AGENT_ID: {
        "testflinger_account": True,
        "dex_account": False,
        "client_id": TESTFLINGER_AGENT_ID,
        "email": "testflinger-agent@example.com",
        "name": "testflinger-agent",
        "role": "agent",
        "allowed_queues": [],
        "max_reservation_time": {},
        "secret_key": "testflinger",  # noqa: S105
    },
    "ci-bot-kernel": {
        "testflinger_account": True,
        "dex_account": False,
        "client_id": "ci-bot-kernel",
        "email": "alice@example.com",
        "role": "contributor",
        "allowed_queues": [],
        "max_reservation_time": {},
        "secret_key": "testflinger",  # noqa: S105
    },
    "ci-bot-snapd": {
        "testflinger_account": True,
        "dex_account": True,
        "client_id": "ci-bot-snapd",
        "email": "bob@example.com",
        "name": "bob",
        "sub": "1004",
        "role": "manager",
        "allowed_queues": [],
        "max_reservation_time": {},
        "secret_key": "testflinger",  # noqa: S105
    },
    "qa-runner-x86": {
        "testflinger_account": True,
        "dex_account": True,
        "client_id": "qa-runner-x86",
        "email": "carol@example.com",
        "name": "carol",
        "sub": "1005",
        "role": "contributor",
        "allowed_queues": [],
        "max_reservation_time": {},
        "secret_key": "testflinger",  # noqa: S105
    },
    "infra-agent-arm": {
        "testflinger_account": True,
        "dex_account": False,
        "client_id": "infra-agent-arm",
        "email": "dave@example.com",
        "role": "contributor",
        "allowed_queues": [],
        "max_reservation_time": {},
        "secret_key": "testflinger",  # noqa: S105
    },
}
