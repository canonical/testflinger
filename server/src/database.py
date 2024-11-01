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

import os
import urllib
from datetime import datetime, timezone
from typing import Any

from flask_pymongo import PyMongo
from gridfs import GridFS, errors


# Constants for TTL indexes
DEFAULT_EXPIRATION = 60 * 60 * 24 * 7  # 7 days
OUTPUT_EXPIRATION = 60 * 60 * 4  # 4 hours

mongo = PyMongo()


def get_mongo_uri():
    """Creates mongodb uri from environment variables"""
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

    return mongo_uri


def setup_mongodb(application):
    """
    Setup mongodb connection if we have valid config data
    Otherwise leave it empty, which means we are probably running unit tests
    """
    mongo_uri = get_mongo_uri()
    mongo.init_app(
        application,
        uri=mongo_uri,
        uuidRepresentation="standard",
        serverSelectionTimeoutMS=2000,
        maxPoolSize=os.environ.get("MONGODB_MAX_POOL_SIZE", 100),
    )

    create_indexes()


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

    # Remove agents that haven't checked in for 7 days
    mongo.db.agents.create_index(
        "updated_at", expireAfterSeconds=DEFAULT_EXPIRATION
    )

    # Remove advertised queues that haven't updated in over 7 days
    mongo.db.queues.create_index(
        "updated_at", expireAfterSeconds=DEFAULT_EXPIRATION
    )

    # Faster lookups for common queries
    mongo.db.jobs.create_index("job_id")
    mongo.db.jobs.create_index(["result_data.job_state", "job_data.job_queue"])


def save_file(data: Any, filename: str):
    """Store a file in the database (using GridFS)"""
    # Normally we would use flask-pymongo save_file but it doesn't seem to
    # work nicely for me with mongomock
    storage = GridFS(mongo.db)
    file_id = storage.put(data, filename=filename)
    # Add a timestamp to the chunks - do this so we can set a TTL for them
    timestamp = mongo.db.fs.files.find_one({"_id": file_id})["uploadDate"]
    mongo.db.fs.chunks.update_many(
        {"files_id": file_id}, {"$set": {"uploadDate": timestamp}}
    )


def retrieve_file(filename):
    """Retrieve a file from the database (using GridFS)"""
    # Normally we would use flask-pymongo send_file but it doesn't seem to
    # work nicely for me with mongomock
    storage = GridFS(mongo.db)
    try:
        return storage.get_last_version(filename=filename)
    except errors.NoFile as error:
        raise FileNotFoundError from error


def get_attachments_status(job_id: str) -> str:
    """Return the attachments status of a job with `job_id`

    :raises:
        `ValueError` if no such job exists
    :returns:
        - None if the job is not awaiting attachments
        - "waiting" if the job is awaiting attachments
        - "complete" if the job has already received attachments
    """
    response = mongo.db.jobs.find_one(
        {
            "job_id": job_id,
            "result_data.job_state": "waiting",
        },
        projection={"_id": False, "job_data": True},
    )
    if response is None:
        raise ValueError(f"{job_id} is not valid")
    return response["job_data"].get("attachments_status")


def attachments_received(job_id):
    """Inform the database that a job attachment archive has been stored"""
    mongo.db.jobs.find_one_and_update(
        {
            "job_id": job_id,
            "job_data.attachments_status": "waiting",
        },
        {"$set": {"job_data.attachments_status": "complete"}},
        projection={},
    )


def add_job(job: dict):
    """Add the `job` to the database"""
    mongo.db.jobs.insert_one(job)


def pop_job(queue_list):
    """Get the next job in the queue"""
    # The queue name and the job are returned, but we don't need the queue now
    try:
        response = mongo.db.jobs.find_one_and_update(
            {
                "result_data.job_state": "waiting",
                "job_data.job_queue": {"$in": queue_list},
                "$or": [
                    {"job_data.attachments_status": {"$exists": False}},
                    {"job_data.attachments_status": "complete"},
                ],
            },
            {"$set": {"result_data.job_state": "running"}},
            projection={
                "job_id": True,
                "created_at": True,
                "job_data": True,
                "_id": True,
            },
            sort=[("job_priority", -1)],
        )
    except TypeError:
        return None
    if not response:
        return None
    # Flatten the job_data and include the job_id
    job = response["job_data"]
    job_id = response["job_id"]
    job["job_id"] = job_id
    # Mark the time the job was started
    started_at = datetime.now(timezone.utc)
    mongo.db.jobs.update_one(
        {"job_id": job_id},
        {"$set": {"started_at": started_at}},
    )
    # Save data about the wait time in the queue
    created_at = response["created_at"]
    queue = job["job_queue"]
    save_queue_wait_time(queue, started_at, created_at)

    return job


def save_queue_wait_time(
    queue: str, started_at: datetime, created_at: datetime
):
    """Save data about the wait time in seconds for the specified queue"""
    # Ensure that python knows both datestamps are in UTC
    started_at = started_at.replace(tzinfo=timezone.utc)
    created_at = created_at.replace(tzinfo=timezone.utc)
    wait_seconds = (started_at - created_at).seconds
    mongo.db.queue_wait_times.update_one(
        {"name": queue},
        {
            "$push": {
                "wait_times": wait_seconds,
            }
        },
        upsert=True,
    )


def get_queue_wait_times(queues: list[str] | None = None) -> list[dict]:
    """Get the percentiles of wait times for specified queues or all queues"""
    if not queues:
        wait_times = mongo.db.queue_wait_times.find({}, {"_id": False})
    else:
        wait_times = mongo.db.queue_wait_times.find(
            {"name": {"$in": queues}}, {"_id": False}
        )
    return list(wait_times)


def calculate_percentiles(data: list) -> dict:
    """
    Calculate the percentiles of the wait times for each queue

    This uses the nearest rank with interpolation method, which can help in
    cases where the data is not evenly distributed, such as when we might
    have big gaps between the best and worst case scenarios.
    """
    if not data:
        return {}
    percentiles = [5, 10, 50, 90, 95]
    data.sort()
    percentile_results = {}
    for percentile in percentiles:
        # Index is the position in our sorted data that goes with this
        # percentile
        index = (len(data) - 1) * (percentile / 100.0)
        # Lower and upper index are the indexes of two closest data points
        # that are below and above the percentile
        lower_index = int(index)
        upper_index = lower_index + 1
        if upper_index < len(data):
            # Interpolate the value based on how far the lower and upper
            # data points are from the percentile
            lower_value = data[lower_index] * (upper_index - index)
            upper_value = data[upper_index] * (index - lower_index)
            percentile_results[percentile] = lower_value + upper_value
        else:
            # If the upper index is out of bounds, just use the lower value
            percentile_results[percentile] = data[lower_index]
    return percentile_results


def get_provision_log(
    agent_id: str, start_datetime: datetime, stop_datetime: datetime
) -> list:
    """Get the provision log for an agent between two dates"""
    provision_log_entries = mongo.db.provision_logs.aggregate(
        [
            {"$match": {"name": agent_id}},
            {
                "$project": {
                    "provision_log": {
                        "$filter": {
                            "input": "$provision_log",
                            "as": "log",
                            "cond": {
                                "$and": [
                                    {
                                        "$gte": [
                                            "$$log.timestamp",
                                            start_datetime,
                                        ]
                                    },
                                    {
                                        "$lt": [
                                            "$$log.timestamp",
                                            stop_datetime,
                                        ]
                                    },
                                ]
                            },
                        }
                    }
                }
            },
        ]
    )
    # Convert the aggregated result to a list of logs
    provision_log_entries = list(provision_log_entries)

    return (
        provision_log_entries[0]["provision_log"]
        if provision_log_entries
        else []
    )
