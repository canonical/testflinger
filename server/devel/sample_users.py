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
        "secret_key": "testflinger",
    },
    {
        "client_id": "ci-bot-kernel",
        "email": "alice@example.com",  # same contact as previous
        "role": "contributor",
        "allowed_queues": [],
        "max_reservation_time": {},
        "secret_key": "testflinger",
    },
    {
        "client_id": "ci-bot-snapd",
        "email": "bob@example.com",
        "role": "contributor",
        "allowed_queues": [],
        "max_reservation_time": {},
        "secret_key": "testflinger",
    },
    {
        "client_id": "qa-runner-x86",
        "email": "carol@example.com",
        "role": "contributor",
        "allowed_queues": [],
        "max_reservation_time": {},
        "secret_key": "testflinger",
    },
    {
        "client_id": "infra-agent-arm",
        "email": "dave@example.com",
        "role": "admin",
        "allowed_queues": [],
        "max_reservation_time": {},
        "secret_key": "testflinger",
    },
]