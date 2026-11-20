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

Each entry independently enables a Testflinger credential account, a Dex
OIDC account, and a development sign-in menu entry. The credential and Dex
accounts are separate Mongo records and may share an email address.
"""

import base64

DEX_CONNECTOR_ID = "local"


def dex_subject(user_id: str, connector_id: str = DEX_CONNECTOR_ID) -> str:
    """Return the ``sub`` claim Dex issues for a static password user.

    Dex does not return the configured ``userID`` as ``sub``. It returns a
    base64url (unpadded) protobuf message holding the user ID and connector
    ID. Each sample entry keeps the raw ID as ``dex_user_id``.
    """

    def field(tag: int, value: str) -> bytes:
        data = value.encode()
        return bytes([tag, len(data)]) + data

    raw = field(0x0A, user_id) + field(0x12, connector_id)
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


TESTFLINGER_ADMIN_ID = "testflinger-admin"
TESTFLINGER_AGENT_ID = "testflinger-agent"

SAMPLE_CLIENTS = {
    TESTFLINGER_ADMIN_ID: {
        "testflinger_account": True,
        "dex_account": True,
        "dev_auto_signin": True,
        "client_id": TESTFLINGER_ADMIN_ID,
        "email": "testflinger@example.com",
        "name": "testflinger-admin",
        "dex_user_id": "1001",
        "sub": dex_subject("1001"),
        "role": "admin",
        "max_priority": {"*": 100},
        "allowed_queues": [],
        "max_reservation_time": {},
        "secret_key": "testflinger",  # noqa: S105
    },
    "alice-sample-client": {
        "testflinger_account": True,
        "dex_account": True,
        "dev_auto_signin": True,
        "client_id": "alice-sample-client",
        "email": "alice@example.com",
        "name": "alice",
        "dex_user_id": "1003",
        "sub": dex_subject("1003"),
        "role": "admin",
        "allowed_queues": [],
        "max_reservation_time": {},
        "secret_key": "testflinger",  # noqa: S105
    },
    TESTFLINGER_AGENT_ID: {
        "testflinger_account": True,
        "dex_account": False,
        "dev_auto_signin": False,
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
        "dev_auto_signin": False,
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
        "dev_auto_signin": True,
        "client_id": "ci-bot-snapd",
        "email": "bob@example.com",
        "name": "bob",
        "dex_user_id": "1004",
        "sub": dex_subject("1004"),
        "role": "manager",
        "allowed_queues": [],
        "max_reservation_time": {},
        "secret_key": "testflinger",  # noqa: S105
    },
    "qa-runner-x86": {
        "testflinger_account": True,
        "dex_account": True,
        "dev_auto_signin": True,
        "client_id": "qa-runner-x86",
        "email": "carol@example.com",
        "name": "carol",
        "dex_user_id": "1005",
        "sub": dex_subject("1005"),
        "role": "contributor",
        "allowed_queues": [],
        "max_reservation_time": {},
        "secret_key": "testflinger",  # noqa: S105
    },
    "infra-agent-arm": {
        "testflinger_account": True,
        "dex_account": False,
        "dev_auto_signin": False,
        "client_id": "infra-agent-arm",
        "email": "dave@example.com",
        "role": "contributor",
        "allowed_queues": [],
        "max_reservation_time": {},
        "secret_key": "testflinger",  # noqa: S105
    },
}
