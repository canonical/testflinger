# Copyright (C) 2022 Canonical
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
This script administers client credentials in a MongoDB database. Database login
information must be specified with environment variables. The script prompts user
to create a new entry, or edit/delete an existing entry. The user will then be prompted to enter new max_priority and allowed_queues data.

"""

import sys
import json
import bcrypt
import os
import urllib

from pymongo import MongoClient, ReturnDocument


def setup_database():
    mongo_user = os.environ.get("MONGODB_USERNAME")
    mongo_pass = os.environ.get("MONGODB_PASSWORD")
    if mongo_pass:
        # password might contain special chars
        mongo_pass = urllib.parse.quote_plus(mongo_pass)

    mongo_db = os.environ.get("MONGODB_DATABASE")
    mongo_host = os.environ.get("MONGODB_HOST")
    mongo_port = os.environ.get("MONGODB_PORT", "27017")
    mongo_uri = os.environ.get("MONGODB_URI")
    mongo_auth = os.environ.get("MONGODB_AUTH_SOURCE", "admin")

    if not mongo_uri:
        if not (mongo_host and mongo_db):
            raise SystemExit("No MongoDB URI configured!")
        mongo_creds = (
            f"{mongo_user}:{mongo_pass}@" if mongo_user and mongo_pass else ""
        )
        mongo_uri = (
            f"mongodb://{mongo_creds}{mongo_host}:{mongo_port}/{mongo_db}"
            f"?authSource={mongo_auth}"
        )

    client = MongoClient(
        host=mongo_uri,
        username=mongo_user,
        password=mongo_pass,
    )

    return client[mongo_db]


def handle_max_priority_input() -> dict:
    """Gets a user inputted max_priority dict"""
    max_priority = {}
    while True:
        max_priority_input = input(
            "Do you want to specify a max priority for one or more queues? (y/n): "
        )
        if max_priority_input == "y":
            queue_name = input("Enter the name of the queue: ")
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
            "Do you want to specify a list of queues that you are allowed to use? (y/n): "
        )
        if allowed_queues_input == "y":
            queue_name = input("Enter the name of the queue: ")
            allowed_queues.append(queue_name)
        elif allowed_queues_input == "n":
            break
        else:
            print("Invalid input. Please enter 'y' or 'n'.")
    return allowed_queues


def create_client_credential(db):
    """
    Creates new client_id, client_secret pair with max_priority
    and allowed_queues
    """

    client_id = input("Enter the new client_id: ")
    client_secret = input("Enter the new client_secret: ")
    client_secret_hash = bcrypt.hashpw(
        client_secret.encode("utf-8"), bcrypt.gensalt()
    ).decode()

    max_priority = handle_max_priority_input()
    allowed_queues = handle_allowed_queues_input()

    entry = {
        "client_id": client_id,
        "client_secret_hash": client_secret_hash,
        "max_priority": max_priority,
        "allowed_queues": allowed_queues,
    }

    db.client_permissions.insert_one(entry)
    print("Entry has been created and stored in database:")
    print(entry)


def edit_client_credential(db):
    """
    Edits both max_priority and allowed_queues given a client_id. This will
    overwrite both of these lists in the database.
    """

    client_id = input("Enter the client_id you wish to edit: ")
    max_priority = handle_max_priority_input()
    allowed_queues = handle_allowed_queues_input()
    new_entry = db.client_permissions.find_one_and_update(
        {"client_id": client_id},
        {
            "$set": {
                "max_priority": max_priority,
                "allowed_queues": allowed_queues,
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    print("Entry updated successfully: ")
    print(new_entry)


def remove_client_credential(db):
    """Removes a client_id and client_secret pair from the database"""
    client_id = input("Enter the client_id you wish to delete: ")
    result = db.client_permissions.delete_one({"client_id": client_id})
    print("Entry deleted successfully: ")
    print(result)


def main():
    db = setup_database()
    while True:
        user_input = input(
            "Do you wish to create(c), edit(e), or remove(r) a database entry? Enter q to quit "
        )
        if user_input == "c":
            create_client_credential(db)
        elif user_input == "e":
            edit_client_credential(db)
        elif user_input == "r":
            remove_client_credential(db)
        elif user_input == "q":
            sys.exit()
        else:
            print("Invalid selection. Please enter 'c', 'e', or 'r'")


if __name__ == "__main__":
    main()
