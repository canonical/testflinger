# Copyright (C) 2025 Canonical
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

"""Handlers for storing/retrieving agent output and serial output."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List

from testflinger_common.enums import LogType, TestPhase


class LogHandler(ABC):
    """
    Abstract class with methods for storing and retrieving logs
    from a generic backend.
    """

    @abstractmethod
    def store_log_fragment(self, job_id: str, data: str, log_type: LogType):
        """Store log fragments in the handler specific backend."""
        raise NotImplementedError

    @abstractmethod
    def retrieve_log_fragments(
        self,
        job_id: str,
        log_type: LogType,
        phase: TestPhase,
        start_fragment: int = 0,
        start_timestamp: datetime = None,
    ) -> List[dict]:
        """
        Retrieve log fragments from the handler specific backend.
        Log fragment schema can be found in schemas.py.
        """
        raise NotImplementedError

    def retrieve_logs(
        self,
        job_id: str,
        log_type: LogType,
        phase: TestPhase,
        start_fragment: int = 0,
        start_timestamp: datetime = None,
    ) -> dict:
        """
        Return a dictionary with the combined log fragments and the last
        fragment number retrieved.
        """
        fragments = self.retrieve_log_fragments(
            job_id, log_type, phase, start_fragment, start_timestamp
        )
        data_list = [f["log_data"] for f in fragments]
        log_data = "".join(data_list)
        if len(fragments) > 0:
            last_fragment_number = fragments[-1]["fragment_number"]
        else:
            last_fragment_number = -1

        return {
            "last_fragment_number": last_fragment_number,
            "log_data": log_data,
        }


class MongoLogHandler(LogHandler):
    """Implementation of Log Handler for MongoDB backend."""

    def __init__(self, mongo):
        """Initialize mongo db object."""
        self.mongo = mongo

    def store_log_fragment(self, job_id: str, data: dict, log_type: LogType):
        """Store logs in the output/serial_output collection in MongoDB."""
        log_collection = self.mongo.db.logs
        timestamp = datetime.now(timezone.utc)
        data["job_id"] = job_id
        data["log_type"] = log_type
        log_collection.insert_one(
            data,
            {"$set": {"updated_at": timestamp}},
        )

    def retrieve_log_fragments(
        self,
        job_id: str,
        log_type: LogType,
        phase: TestPhase,
        start_fragment: int = 0,
        start_timestamp: datetime = None,
    ) -> List[dict]:
        """Retrieve log fragments from MongoDB sorted by fragment number."""
        log_collection = self.mongo.db.logs
        query = {
            "job_id": job_id,
            "log_type": log_type,
            "phase": phase,
            "fragment_number": {"$gte": start_fragment},
        }
        if start_timestamp is not None:
            query["timestamp"] = {"$gte": start_timestamp}

        return list(log_collection.find(query).sort("fragment_number"))
