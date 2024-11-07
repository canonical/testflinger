# Copyright (C) 2024 Canonical
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

"""
This script administers client credentials in a MongoDB database.
Database login information must be specified with environment
variables. The script prompts user to create a new entry, or
edit/delete an existing entry. The user will then be prompted
to enter new max_priority and allowed_queues data.

"""

import sys
import os
import getpass

import bcrypt
from pymongo import MongoClient, ReturnDocument

from src import database


def setup_database():
    """
    Gets mongo db credentials from environment variables and use them to
    setup a connection to the database
    """
    mongo_uri = database.get_mongo_uri()
    mongo_db = os.environ.get("MONGODB_DATABASE")
    client = MongoClient(
        host=mongo_uri,
    )

    return client[mongo_db]


def handle_max_priority_input() -> dict:
    """Gets a user inputted max_priority dict"""
    max_priority = {}
    while True:
        max_priority_input = input(
            "Do you want to specify a queue to set max priority on? (y/n): "
        )
        if max_priority_input == "y":
            queue_name = input(
                "Enter the name of the queue(* to apply max priority for"
                + " all queues): "
            )
            max_priority[queue_name] = int(
                input("Enter the max priority for this queue: ")
            )
        elif max_priority_input == "n":
            break
        else:
            print("Invalid input. Please enter 'y' or 'n'.")
    return max_priority


def handle_allowed_queues_input() -> list:
    """Gets a user inputted allowed_queues list"""
    allowed_queues = []
    while True:
        allowed_queues_input = input(
            "Do you want to specify a restricted queue that"
            + " you are allowed to use? (y/n): "
        )
        if allowed_queues_input == "y":
            queue_name = input("Enter the name of the queue: ")
            allowed_queues.append(queue_name)
        elif allowed_queues_input == "n":
            break
        else:
            print("Invalid input. Please enter 'y' or 'n'.")
    return allowed_queues


def confirm_dialogue(entry: dict) -> bool:
    """Prompts the user to confirm their changes"""
    print(entry)
    while True:
        confirm = input("Confirm(y/n) that this entry looks correct: ")
        if confirm == "y":
            return True

        if confirm == "n":
            print("operation aborted")
            return False

        print("Enter y/n")


def create_client_credential(db):
    """
    Creates new client_id, client_secret pair with max_priority
    and allowed_queues
    """
    client_id = input("Enter the new client_id: ")
    if (
        db.client_permissions.count_documents(
            {"client_id": client_id}, limit=1
        )
        == 1
    ):
        print("Client id already exists!")
        return

    client_secret = getpass.getpass("Enter the new client_secret: ")
    client_secret_hash = bcrypt.hashpw(
        client_secret.encode("utf-8"), bcrypt.gensalt()
    ).decode()

    max_priority = handle_max_priority_input()
    allowed_queues = handle_allowed_queues_input()

    entry = {
        "client_id": client_id,
        "max_priority": max_priority,
        "allowed_queues": allowed_queues,
    }
    if confirm_dialogue(entry):
        entry["client_secret_hash"] = client_secret_hash
        db.client_permissions.insert_one(entry)
        print("Entry has been created and stored in database")


def edit_client_credential(db):
    """
    Edits both max_priority and allowed_queues given a client_id. This will
    overwrite both of these lists in the database.
    """

    client_id = input("Enter the client_id you wish to edit: ")
    max_priority = handle_max_priority_input()
    allowed_queues = handle_allowed_queues_input()
    confirm_output = confirm_dialogue(
        {
            "client_id": client_id,
            "max_priority": max_priority,
            "allowed_queues": allowed_queues,
        }
    )
    if confirm_output:
        db.client_permissions.find_one_and_update(
            {"client_id": client_id},
            {
                "$set": {
                    "max_priority": max_priority,
                    "allowed_queues": allowed_queues,
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        print("Entry updated successfully")


def remove_client_credential(db):
    """Removes a client_id and client_secret pair from the database"""
    client_id = input("Enter the client_id you wish to delete: ")
    if confirm_dialogue({"client_id": client_id}):
        db.client_permissions.delete_one({"client_id": client_id})
        print("Entry deleted successfully")


def add_restricted_queue(db):
    """Adds a restricted queue to the database"""
    queue_name = input("Enter the name of the restricted queue to add: ")
    queue_entry = {"queue_name": queue_name}
    if confirm_dialogue(queue_entry):
        queue_exists_num = db.restricted_queues.count_documents(
            queue_entry, limit=1
        )
        if queue_exists_num != 0:
            print("Restricted queue already exists!")
            return
        db.restricted_queues.insert_one(queue_entry)
        print("Restricted queue sucessfully added")


def remove_restricted_queue(db):
    """Removes a restricted queue from the database"""
    queue_name = input("Enter the client_id you wish to delete: ")
    queue_entry = {"queue_name": queue_name}
    if confirm_dialogue(queue_entry):
        db.restricted_queues.delete_one(queue_entry)
        print("Entry deleted successfully")


def main():
    """
    Initial command line interface for adding client info and
    restricted queues
    """
    db = setup_database()
    while True:
        user_input = input(
            "Do you wish to create(c), edit(e), or remove(r) a client?"
            + " You can also add a restricted queue(aq)"
            + " or remove a restricted queue(rq). Enter q to quit: "
        )
        if user_input == "c":
            create_client_credential(db)
        elif user_input == "e":
            edit_client_credential(db)
        elif user_input == "r":
            remove_client_credential(db)
        elif user_input == "aq":
            add_restricted_queue(db)
        elif user_input == "rq":
            remove_restricted_queue(db)
        elif user_input == "q":
            sys.exit()
        else:
            print(
                "Invalid selection. Please enter 'c', 'e', 'r', 'aq', or 'rq'"
            )


if __name__ == "__main__":
    main()
