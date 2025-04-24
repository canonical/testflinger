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
Administer client credentials in a MongoDB database.
Database login information must be specified with environment
variables. The script prompts user to create a new entry, or
edit/delete an existing entry. The user will then be prompted
to enter new max_priority and allowed_queues data.

"""

import getpass
import os
import sys

import bcrypt
from pymongo import MongoClient, ReturnDocument

from testflinger import database


def setup_database():
    """
    Get mongo db credentials from environment variables and use them to
    setup a connection to the database
    """
    mongo_uri = database.get_mongo_uri()
    mongo_db = os.environ.get("MONGODB_DATABASE")
    client = MongoClient(
        host=mongo_uri,
    )

    return client[mongo_db]


def handle_max_priority_input() -> dict:
    """Get a user inputted max_priority dict"""
    max_priority = {}
    while True:
        max_priority_input = input(
            "Do you want to specify a queue to set max priority on? (y/n): "
        )
        if max_priority_input == "y":
            queue_name = input(
                "Enter the name of the queue(* to apply max priority for "
                "all queues): ",
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
    """Get a user inputted allowed_queues list"""
    allowed_queues = []
    while True:
        allowed_queues_input = input(
            "Do you want to specify a restricted queue that "
            "you are allowed to use? (y/n): "
        )
        if allowed_queues_input == "y":
            queue_name = input("Enter the name of the queue: ")
            allowed_queues.append(queue_name)
        elif allowed_queues_input == "n":
            break
        else:
            print("Invalid input. Please enter 'y' or 'n'.")
    return allowed_queues


def handle_max_reservation_input() -> list:
    """Get a user inputted max_reservation_time dict"""
    max_reservation = {}
    while True:
        max_reservation_input = input(
            "Do you want to specify a queue to set "
            "max reservation time for? (y/n): "
        )
        if max_reservation_input.lower() == "y":
            queue_name = input(
                "Enter the name of the queue "
                "(* to apply max reservation for all queues): "
            )
            while True:
                try:
                    max_reservation[queue_name] = int(
                        input(
                            "Enter the maximum reservation time "
                            "for this queue: "
                        )
                    )
                    break
                except ValueError:
                    print("Please enter a valid integer value")
        elif max_reservation_input.lower() == "n":
            break
        else:
            print("Invalid input. Please enter 'y' or 'n'.")
    return max_reservation


def confirm_dialogue(entry: dict) -> bool:
    """Prompt the user to confirm their changes"""
    print(entry)
    while True:
        confirm = input("Confirm that this entry looks correct (y/n): ")
        if confirm == "y":
            return True

        if confirm == "n":
            print("operation aborted")
            return False

        print("Enter y/n")


def check_client_exists(db, client_id: str) -> bool:
    """Check if client id exists in client_permissions"""
    return (
        db.client_permissions.count_documents(
            {"client_id": client_id}, limit=1
        )
        != 0
    )


def create_client_credential(db):
    """
    Create new client_id, client_secret pair with max_priority
    and allowed_queues
    """
    client_id = input("Enter the new client_id: ")
    if check_client_exists(db, client_id):
        print("Client id already exists!\n")
        return

    client_secret = getpass.getpass("Enter the new client_secret: ")
    client_secret_confirm = getpass.getpass(
        "Enter the new client_secret again: "
    )
    if client_secret != client_secret_confirm:
        print("New client secrets do not match!\n")
        return

    client_secret_hash = bcrypt.hashpw(
        client_secret.encode("utf-8"), bcrypt.gensalt()
    ).decode()

    max_priority = handle_max_priority_input()
    allowed_queues = handle_allowed_queues_input()
    max_reservation = handle_max_reservation_input()

    entry = {
        "client_id": client_id,
        "max_priority": max_priority,
        "allowed_queues": allowed_queues,
        "max_reservation_time": max_reservation,
    }
    if confirm_dialogue(entry):
        entry["client_secret_hash"] = client_secret_hash
        db.client_permissions.insert_one(entry)
        print("Entry has been created and stored in database\n")


def edit_client_credential(db):
    """
    Edit both max_priority and allowed_queues given a client_id. This will
    overwrite both of these lists in the database.
    """
    client_id = input("Enter the client_id you wish to edit: ")
    if not check_client_exists(db, client_id):
        print("Client id not in database!\n")
        return

    max_priority = handle_max_priority_input()
    allowed_queues = handle_allowed_queues_input()
    max_reservation = handle_max_reservation_input()
    confirm_output = confirm_dialogue(
        {
            "client_id": client_id,
            "max_priority": max_priority,
            "allowed_queues": allowed_queues,
            "max_reservation_time": max_reservation,
        }
    )
    if confirm_output:
        db.client_permissions.find_one_and_update(
            {"client_id": client_id},
            {
                "$set": {
                    "max_priority": max_priority,
                    "allowed_queues": allowed_queues,
                    "max_reservation_time": max_reservation,
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        print("Entry updated successfully\n")


def remove_client_credential(db):
    """Remove a client_id and client_secret pair from the database"""
    client_id = input("Enter the client_id you wish to delete: ")
    if not check_client_exists(db, client_id):
        print("Client id not in database!\n")
        return

    if confirm_dialogue({"client_id": client_id}):
        db.client_permissions.delete_one({"client_id": client_id})
        print("Entry deleted successfully\n")


def check_queue_exists(db, queue_name: str) -> bool:
    """Check if queue is in the restricted_queues collection"""
    return (
        db.restricted_queues.count_documents(
            {"queue_name": queue_name}, limit=1
        )
        != 0
    )


def add_restricted_queue(db):
    """Add a restricted queue to the database"""
    queue_name = input("Enter the name of the restricted queue to add: ")
    if check_queue_exists(db, queue_name):
        print("Restricted queue already exists!\n")
        return

    queue_entry = {"queue_name": queue_name}
    if confirm_dialogue(queue_entry):
        db.restricted_queues.insert_one(queue_entry)
        print("Restricted queue sucessfully added\n")


def remove_restricted_queue(db):
    """Remove a restricted queue from the database"""
    queue_name = input(
        "Enter the name of the restricted queue you wish to delete: "
    )
    if not check_queue_exists(db, queue_name):
        print("Restricted queue not in database!\n")
        return

    queue_entry = {"queue_name": queue_name}
    if confirm_dialogue(queue_entry):
        db.restricted_queues.delete_one(queue_entry)
        print("Entry deleted successfully\n")


def add_list_restricted_queues(db):
    """Add a comma separated list of restricted queues to the database"""
    queue_list_str = input(
        "Enter a comma separated list of restricted queues to add: "
    )
    queue_list = queue_list_str.split(",")
    existing_queues = [q for q in queue_list if check_queue_exists(db, q)]
    print(
        "Some queues were already found.",
        f"They will be skipped: {existing_queues}",
    )
    queue_entry = [
        {"queue_name": q} for q in queue_list if not check_queue_exists(db, q)
    ]
    print(f"{len(queue_entry)} queues to add")
    if confirm_dialogue(queue_entry):
        db.restricted_queues.insert_many(queue_entry)


def main():
    """
    Command line interface for adding client info and
    restricted queues
    """
    db = setup_database()
    while True:
        print("(c) Create client")
        print("(e) Edit client")
        print("(r) Remove client")
        print("(aq) Add restricted queue")
        print("(rq) Remove restricted queue")
        print("(al) Add comma separated list of restricted queues")
        print("(q) Quit")

        user_input = input("Enter your selection: ")
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
        elif user_input == "al":
            add_list_restricted_queues(db)
        elif user_input == "q":
            sys.exit()
        else:
            print(
                "Invalid selection. Please enter "
                "'c', 'e', 'r', 'aq', 'rq', 'al', or 'q'\n"
            )


if __name__ == "__main__":
    main()
