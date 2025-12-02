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
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Iterable

from testflinger_common.enums import LogType, TestPhase


@dataclass
class LogFragment:
    """Class representing fragment of log in database."""

    job_id: str
    log_type: LogType
    phase: TestPhase
    fragment_number: int
    timestamp: datetime
    log_data: str


class LogHandler(ABC):
    """
    Abstract class with methods for storing and retrieving logs
    from a generic backend.
    """

    @abstractmethod
    def store_log_fragment(self, log_fragment: LogFragment):
        """Store log fragments in the handler-specific backend."""
        raise NotImplementedError

    @abstractmethod
    def retrieve_log_fragments(
        self,
        job_id: str,
        log_type: LogType,
        phase: TestPhase,
        start_fragment: int = 0,
        start_timestamp: datetime = None,
    ) -> Iterable[LogFragment]:
        """
        Retrieve log fragments from the handler-specific backend.
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
        fragments = list(
            self.retrieve_log_fragments(
                job_id, log_type, phase, start_fragment, start_timestamp
            )
        )

        log_data = "".join([f.log_data for f in fragments])
        if len(fragments) > 0:
            last_fragment_number = fragments[-1].fragment_number
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

    def store_log_fragment(self, log_fragment: LogFragment):
        """Store logs in the approriate log collection in MongoDB."""
        log_collection = self.mongo.db.logs
        fragment_dict = asdict(log_fragment)
        timestamp = datetime.now(timezone.utc)
        if fragment_dict["timestamp"] is None:
            fragment_dict["timestamp"] = timestamp
        fragment_dict["updated_at"] = timestamp
        log_collection.insert_one(fragment_dict)

    def retrieve_log_fragments(
        self,
        job_id: str,
        log_type: LogType,
        phase: TestPhase,
        start_fragment: int = 0,
        start_timestamp: datetime = None,
    ) -> Iterable[LogFragment]:
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

        yield from (
            LogFragment(
                fragment["job_id"],
                fragment["log_type"],
                fragment["phase"],
                fragment["fragment_number"],
                fragment["timestamp"],
                fragment["log_data"],
            )
            for fragment in log_collection.find(query).sort("fragment_number")
        )

    def format_logs_as_results(self, job_id: str, result_data: dict) -> dict:
        """Format logs stored in MongoDB into the result_data structure."""
        # Reconstruct result format with logs and phase statuses
        result_logs = {
            phase + "_" + log_type: log_data
            for log_type in LogType
            for phase in TestPhase
            if (
                log_data := self.retrieve_logs(job_id, log_type, phase)[
                    "log_data"
                ]
            )
        }
        phase_status = result_data.pop("status", {})
        result_status = {
            phase + "_status": status
            for phase in TestPhase
            if (status := phase_status.get(phase)) is not None
        }

        # Update result_data with reconstructed fields
        result_data.update(result_logs | result_status)
        return result_data
