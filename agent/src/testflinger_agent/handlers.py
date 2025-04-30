# Copyright (C) 2024 Canonical
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from .client import TestflingerClient, LogEndpointInput


class LogHandler(ABC):
    """Abstract callable class that receives live log updates"""

    @abstractmethod
    def __call__(self, data: str):
        raise NotImplementedError


class FileLogHandler(LogHandler):
    """
    Implementation of LogHandler that writes live log updates
    to a file.
    """

    def __init__(self, filename: str):
        self.log_file = filename

    def __call__(self, data: str):
        with open(self.log_file, "a") as log:
            log.write(data)


class EndpointLogHandler(LogHandler):
    """
    Abstract class that writes live log updates to a generic endpoint
    in Testflinger server.
    """

    def __init__(self, client: TestflingerClient, job_id: str, phase: str):
        self.fragment_number = 0
        self.client = client
        self.phase = phase
        self.job_id = job_id

    @abstractmethod
    def write_to_endpoint(self, data_dict: LogEndpointInput):
        raise NotImplementedError

    def __call__(self, data: str):
        data_dict: LogEndpointInput = {
            "fragment_number": self.fragment_number,
            "timestamp": str(datetime.now(timezone.utc)),
            "phase": self.phase,
            "log_data": data,
        }
        self.write_to_endpoint(data_dict)
        self.fragment_number += 1


class OutputLogHandler(EndpointLogHandler):
    """
    Implementation of EndpointLogHandler that writes logs to the output
    endpoint in Testflinger server.
    """

    def write_to_endpoint(self, data_dict: LogEndpointInput):
        self.client.post_output(self.job_id, data_dict)


class SerialLogHandler(EndpointLogHandler):
    """
    Implementation of EndpointLogHandler that writes logs to the serial
    endpoint in Testflinger server.
    """

    def write_to_endpoint(self, data_dict: LogEndpointInput):
        self.client.post_serial(self.job_id, data_dict)
