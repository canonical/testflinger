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
This returns a db object for talking to MongoDB
"""

from flask_pymongo import PyMongo

# Constants for TTL indexes
DEFAULT_EXPIRATION = 60 * 60 * 24 * 7  # 7 days
OUTPUT_EXPIRATION = 60 * 60 * 4  # 4 hours

mongo = PyMongo()


def create_indexes():
    """Initialize collections and indexes in case they don't exist already"""

    # Automatically expire jobs after 7 days if nothing runs them
    mongo.db.jobs.create_index(
        "created_at", expireAfterSeconds=DEFAULT_EXPIRATION
    )

    # Remove output 4 hours after the last entry if nothing polls for it
    mongo.db.output.create_index(
        "updated_at", expireAfterSeconds=OUTPUT_EXPIRATION
    )

    # Remove artifacts after 7 days
    mongo.db.fs.chunks.create_index(
        "uploadDate", expireAfterSeconds=DEFAULT_EXPIRATION
    )
    mongo.db.fs.files.create_index(
        "uploadDate", expireAfterSeconds=DEFAULT_EXPIRATION
    )
