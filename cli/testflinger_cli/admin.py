# Copyright (C) 2020-2022 Canonical
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
#

"""Testflinger Admin CLI module."""

import sys
from http import HTTPStatus

from testflinger_cli import client
from testflinger_cli.auth import require_role


class TestflingerAdminCLI:
    """Class for handling all admin CLI commands."""

    def __init__(self, subparsers, main_cli):
        self.main_cli = main_cli

        parser = subparsers.add_parser(
            "admin",
            help="Admin commands. Requires authentication",
        )
        admin_subparser = parser.add_subparsers(
            dest="admin_command", required=True
        )
        self._add_set_args(admin_subparser)

    def _add_set_args(self, subparsers):
        """Command line arguments for set action."""
        parser = subparsers.add_parser(
            "set", help="Perform set action on subcommand"
        )
        set_subparser = parser.add_subparsers(
            dest="set_command", required=True
        )
        self._add_set_agent_status_args(set_subparser)

    def _add_set_agent_status_args(self, subparsers):
        """Command line arguments for agent status."""
        parser = subparsers.add_parser(
            "agent-status", help="Modify agent status"
        )
        parser.set_defaults(func=self.set_agent_status)
        parser.add_argument(
            "--status",
            required=True,
            choices=["online", "offline", "maintenance"],
            help="Status to set for the agent(s)",
        )
        parser.add_argument(
            "agent_list",
            nargs="+",
            help="List of agents to modify their status",
        )
        parser.add_argument(
            "--comment",
            help="Reason for modifying status. "
            "Required when changing status to offline.",
        )
        parser.add_argument(
            "--client_id",
            default=None,
            help="Client ID to authenticate with Testflinger server",
        )
        parser.add_argument(
            "--secret_key",
            default=None,
            help="Secret key to be used with client id for authentication",
        )

    @require_role("admin")
    def set_agent_status(self):
        """Modify agent status."""
        agents = self.main_cli.args.agent_list

        # Override online for valid state in server
        status_override = {"online": "waiting"}
        status = status_override.get(
            self.main_cli.args.status, self.main_cli.args.status
        )
        client_id = self.main_cli.auth.client_id

        # Creating dictonary to define formmated comments
        comment_dict = {
            "waiting": lambda _, __: "",
            "offline": lambda user,
            comment: f"Set to offline by {user}. Reason: {comment}",
            "maintenance": lambda user,
            _: f"Set to offline by {user} for lab related task.",
        }

        # Exiting if no comment specified when changing agent status to offline
        if status == "offline" and not self.main_cli.args.comment:
            sys.exit(
                "Comment is required when setting agent status to offline."
            )

        # Defining test phases
        test_status = ["setup", "provision", "test", "allocate", "reserve"]

        for agent in agents:
            comment = comment_dict[status](
                client_id, self.main_cli.args.comment
            )
            agent_status = self.main_cli.client.get_agent_data(agent)["state"]
            # Do not change to waiting if device is under test phase
            if agent_status in test_status and status == "waiting":
                print(f"Could not modify {agent} in its current state")
                continue
            try:
                self.main_cli.client.set_agent_status(agent, status, comment)
                if agent_status in test_status:
                    print(
                        f"Agent {agent} processing job. "
                        f"Status {status} deferred until job completion"
                    )
                else:
                    print(f"Agent {agent} status is now: {status}")
            except client.HTTPError as exc:
                if exc.status == HTTPStatus.NOT_FOUND:
                    print(f"Agent {agent} does not exist.")
