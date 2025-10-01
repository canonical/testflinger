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

import json
import logging
import sys
from http import HTTPStatus
from string import Template

from testflinger_cli import client
from testflinger_cli.auth import require_role
from testflinger_cli.consts import ServerRoles

logger = logging.getLogger(__name__)


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
        self._add_get_args(admin_subparser)
        self._add_delete_args(admin_subparser)
        self._add_update_args(admin_subparser)

    def _add_set_args(self, subparsers):
        """Command line arguments for set action."""
        parser = subparsers.add_parser(
            "set", help="Perform set action on subcommand"
        )
        set_subparser = parser.add_subparsers(
            dest="set_command", required=True
        )
        self._add_set_agent_status_args(set_subparser)
        self._add_set_client_permissions_args(set_subparser)

    def _add_get_args(self, subparsers):
        """Command line arguments for set action."""
        parser = subparsers.add_parser(
            "get", help="Perform get action on subcommand"
        )
        get_subparser = parser.add_subparsers(
            dest="get_command", required=True
        )
        self._add_get_client_permissions_args(get_subparser)

    def _add_delete_args(self, subparsers):
        """Command line arguments for set action."""
        parser = subparsers.add_parser(
            "delete", help="Perform delete action on subcommand"
        )
        delete_subparser = parser.add_subparsers(
            dest="delete_command", required=True
        )
        self._add_delete_client_permissions_args(delete_subparser)

    def _add_update_args(self, subparsers):
        """Command line arguments for update action."""
        parser = subparsers.add_parser(
            "update", help="Perform update action on subcommand"
        )
        update_subparser = parser.add_subparsers(
            dest="update_command", required=True
        )
        self._add_update_client_permissions_args(update_subparser)

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
            "--agents",
            required=True,
            action="extend",
            nargs="+",
            help="Agents to modify the status on",
        )
        parser.add_argument(
            "--comment",
            help="Reason for modifying status (required for status offline)",
        )
        self.main_cli._add_auth_args(parser)

    def _add_set_client_permissions_args(self, subparsers):
        parser = subparsers.add_parser(
            "client-permissions", help="Set permissions for a client_id"
        )
        parser.set_defaults(func=self.set_client_permissions)
        parser.add_argument(
            "--testflinger-client-id",
            help="Client_id to set permissions",
        )
        parser.add_argument(
            "--testflinger-client-secret",
            help="Secret key to be defined for client_id",
        )
        parser.add_argument(
            "--max-priority",
            help="Max priority defined for specified queues for client_id",
            default="{}",
        )
        parser.add_argument(
            "--max-reservation",
            help="Max reservation time defined specified queues for client_id",
            default="{}",
        )
        parser.add_argument(
            "--role",
            help="Role defined for client_id",
            choices=[
                ServerRoles.ADMIN,
                ServerRoles.MANAGER,
                ServerRoles.CONTRIBUTOR,
            ],
            default=ServerRoles.CONTRIBUTOR,
        )
        parser.add_argument(
            "--json", help="Optional JSON data with client_permissions"
        )
        self.main_cli._add_auth_args(parser)

    def _add_get_client_permissions_args(self, subparsers):
        parser = subparsers.add_parser(
            "client-permissions", help="Get permissions for client_id"
        )
        parser.set_defaults(func=self.get_client_permissions)
        parser.add_argument(
            "--testflinger-client-id",
            help="Client_id to get permissions",
        )
        self.main_cli._add_auth_args(parser)

    def _add_delete_client_permissions_args(self, subparsers):
        parser = subparsers.add_parser(
            "client-permissions",
            help="Delete client_id registry from database",
        )
        parser.set_defaults(func=self.delete_client_permissions)
        parser.add_argument(
            "--testflinger-client-id",
            required=True,
            help="client_id to delete from database",
        )
        self.main_cli._add_auth_args(parser)

    def _add_update_client_permissions_args(self, subparsers):
        parser = subparsers.add_parser(
            "client-permissions", help="Set permissions for a client_id"
        )
        parser.set_defaults(func=self.update_client_permissions)
        parser.add_argument(
            "--testflinger-client-id",
            help="Client_id to set permissions",
        )
        parser.add_argument(
            "--testflinger-client-secret",
            help="Secret key to be defined for client_id",
        )
        parser.add_argument(
            "--max-priority",
            help="Max priority defined for specified queues for client_id",
        )
        parser.add_argument(
            "--max-reservation",
            help="Max reservation time defined specified queues for client_id",
        )
        parser.add_argument(
            "--role",
            help="Role defined for client_id",
            choices=[
                ServerRoles.ADMIN,
                ServerRoles.MANAGER,
                ServerRoles.CONTRIBUTOR,
            ],
        )
        parser.add_argument(
            "--json", help="Optional JSON data with client_permissions"
        )
        self.main_cli._add_auth_args(parser)

    @require_role(ServerRoles.ADMIN)
    def set_agent_status(self):
        """Modify agent status."""
        # Override online for valid state in server
        status_override = {"online": "waiting"}
        status = status_override.get(
            self.main_cli.args.status, self.main_cli.args.status
        )
        client_id = self.main_cli.auth.client_id

        # Creating dictionary to define formmated comments
        comment_templates = {
            "waiting": Template(""),
            "offline": Template("Set to offline by $user. Reason: $comment"),
            "maintenance": Template(
                "Set to offline by $user for lab-related task."
            ),
        }

        # Exiting if no comment specified when changing agent status to offline
        if status == "offline" and not self.main_cli.args.comment:
            sys.exit(
                "Comment is required when setting agent status to offline."
            )

        # Defining test phases
        test_status = ["setup", "provision", "test", "allocate", "reserve"]

        for agent in self.main_cli.args.agents:
            comment = comment_templates[status].substitute(
                user=client_id,
                comment=self.main_cli.args.comment,
            )

            # Get agent status, skip if agent doesn't exist
            try:
                agent_status = self.main_cli.client.get_agent_data(agent)[
                    "state"
                ]
            except client.HTTPError as exc:
                if exc.status == HTTPStatus.NOT_FOUND:
                    print(f"Agent {agent} does not exist.")
                else:
                    print(
                        "Exception raised when setting "
                        f"status for {agent}: {exc}"
                    )
                continue

            # Do not change to waiting if device is under test phase
            if agent_status in test_status and status == "waiting":
                print(f"Could not modify {agent} in its current state")
                continue

            # Set the agent status
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
                else:
                    print(
                        "Exception raised when setting "
                        f"status for {agent}: {exc}"
                    )

    def _parse_client_permissions(self):
        """Parse client permissions provided by JSON or single arguments.

        :return: Parsed json data from provided CLI arguments.
        """
        # Build json_data, if provided json takes precedence
        if self.main_cli.args.json:
            try:
                # Handle both string and already parsed JSON
                if isinstance(self.main_cli.args.json, str):
                    json_data = json.loads(self.main_cli.args.json)
                else:
                    json_data = self.main_cli.args.json
            except (json.JSONDecodeError, TypeError) as exc:
                sys.exit(f"Error parsing JSON: {exc}")
        else:
            # Build from individual arguments
            args_mapping = {
                "client_id": "testflinger_client_id",
                "client_secret": "testflinger_client_secret",
                "max_priority": "max_priority",
                "max_reservation_time": "max_reservation",
                "role": "role",
            }

            json_data = {
                json_key: getattr(self.main_cli.args, arg_name)
                for json_key, arg_name in args_mapping.items()
                if getattr(self.main_cli.args, arg_name) is not None
            }

            # Parse JSON strings for dictionary fields
            for field in ["max_priority", "max_reservation_time"]:
                if field in json_data:
                    try:
                        json_data[field] = json.loads(json_data[field])
                    except (json.JSONDecodeError, TypeError) as exc:
                        sys.exit(f"Error parsing {field} JSON: {exc}")

        return json_data

    @require_role(ServerRoles.ADMIN, ServerRoles.MANAGER)
    def set_client_permissions(self):
        """Set permissions for specified clients."""
        # Get the authentication header to perform authenticated request
        auth_header = self.main_cli.auth.build_headers()

        # Obtain JSON data from args for new client creation
        json_data = self._parse_client_permissions()

        # Get client_id for existence check in provided data
        tf_client_id = json_data.get("client_id")
        if not tf_client_id:
            sys.exit("Error: client_id cannot be empty")

        # Check if client already exists
        try:
            self.main_cli.client.get_client_permissions(
                auth_header, tf_client_id
            )

            # Client exists if check succeeds, log an error and exit
            logger.error(
                "Client id %s already exists. For updating "
                "client permissions, please use the update command.",
                tf_client_id,
            )
            return
        except client.HTTPError as exc:
            if exc.status != HTTPStatus.NOT_FOUND:
                # If any other HTTP error, checking client existance failed
                logger.error(
                    "Error while trying to check client existence: %s", exc.msg
                )
                return

        # If we got here, the client id doesn't exist, attempt to create
        print(f"Creating new client '{tf_client_id}'...")
        try:
            self.main_cli.client.create_client_permissions(
                auth_header, json_data
            )
            print(f"Client '{tf_client_id}' created successfully")
        except client.HTTPError as exc:
            if exc.status == HTTPStatus.UNPROCESSABLE_ENTITY:
                # Schema validation failed
                # Failure reason is clearly stated in msg from server
                logger.error(exc.msg)
            else:
                logger.error(
                    "Failed to create client: %s",
                    exc.msg,
                )

    @require_role(ServerRoles.ADMIN, ServerRoles.MANAGER)
    def update_client_permissions(self):
        """Update provided permissions for specified client."""
        # Get the authentication header to perform authenticated PUT request
        auth_header = self.main_cli.auth.build_headers()

        # Provided JSON data can be single or multiple values to edit
        json_data = self._parse_client_permissions()
        tf_client_id = json_data.get("client_id")

        if not tf_client_id:
            sys.exit("Error: client_id cannot be empty")

        try:
            # Get current client permissions
            current_permissions = self.main_cli.client.get_client_permissions(
                auth_header, tf_client_id
            )

            updated_permissions = current_permissions.copy()
            updated_permissions.update(json_data)

            self.main_cli.client.edit_client_permissions(
                auth_header, updated_permissions
            )
            print(f"Client '{tf_client_id}' permissions updated successfully")
        except client.HTTPError as exc:
            if exc.status == HTTPStatus.NOT_FOUND:
                logger.error(
                    "Provided testflinger client_id does not exists. "
                    "For creating a new client, please use the set command."
                )
            elif exc.status == HTTPStatus.UNPROCESSABLE_ENTITY:
                # Schema validation failed
                # Failure reason is clearly stated in msg from server
                logger.error(exc.msg)

    @require_role(ServerRoles.ADMIN, ServerRoles.MANAGER)
    def get_client_permissions(self):
        """Get permissions for specified clients."""
        # Get the authentication header to perform authenticated GET request
        auth_header = self.main_cli.auth.build_headers()

        # If no client_id specified will get all client_permissions
        tf_client_id = getattr(
            self.main_cli.args, "testflinger_client_id", None
        )
        try:
            print(
                json.dumps(
                    self.main_cli.client.get_client_permissions(
                        auth_header, tf_client_id
                    )
                )
            )
        except client.HTTPError as exc:
            if exc.status == HTTPStatus.NOT_FOUND:
                # Failure reason is clearly stated in msg from server
                logger.error(exc.msg)

    @require_role(ServerRoles.ADMIN)
    def delete_client_permissions(self):
        """Delete specified clients from client_permissions database."""
        # Get the authentication header to perform authenticated DELETE request
        auth_header = self.main_cli.auth.build_headers()

        tf_client = self.main_cli.args.testflinger_client_id
        try:
            self.main_cli.client.delete_client_permissions(
                auth_header, tf_client
            )
            print(f"Succesfully deleted {tf_client} from database")
        except client.HTTPError as exc:
            if (
                exc.status == HTTPStatus.NOT_FOUND
                or exc.status == HTTPStatus.UNPROCESSABLE_ENTITY
            ):
                # Failure reason is clearly stated in msg from server
                logger.info(exc.msg)
