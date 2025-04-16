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

from testflinger_common.enums import LogType

from .client import LogEndpointInput, TestflingerClient


class LogHandler(ABC):
    """Abstract callable class that receives live log updates."""

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


class AgentStatusHandler:
    """Handler to determine if restart is needed at any stage of the agent."""

    def __init__(self):
        """Initialize handler with default values."""
        self._needs_restart = False
        self._needs_offline = False
        self._comment = ""

    def update(
        self,
        comment: str,
        restart: bool = False,
        offline: bool = False,
    ) -> None:
        """Update the attributes of the class if needed.

        :param restart: Flag to set if agent needs restarting.
        :param offline: Flag to set if agent needs offlining.
        :param comment: Reason for requesting agent status change.
        """
        # Update restart flag and comment if not already marked for restart.
        if restart and not self._needs_restart:
            self._needs_restart = True
            if not self._needs_offline:
                self._comment = comment
        # Update offline flag and comment if not already marked for offline.
        if offline and not self._needs_offline:
            self._needs_offline = True
            self._comment = comment
        # Clear the flag and comment if received an offline False
        elif not offline and self._needs_offline:
            self._needs_offline = False
            self._comment = ""

    @property
    def needs_restart(self) -> bool:
        """Indicate the current restart state."""
        return self._needs_restart

    @property
    def needs_offline(self) -> bool:
        """Indicate the current offline state."""
        return self._needs_offline

    @property
    def comment(self) -> str:
        """Retrieve the comment on the state."""
        return self._comment


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
    def write_to_endpoint(self, data: LogEndpointInput):
        raise NotImplementedError

    def __call__(self, data: str):
        log_input = LogEndpointInput(
            self.fragment_number,
            datetime.now(timezone.utc).isoformat(),
            self.phase,
            data,
        )
        self.write_to_endpoint(log_input)
        self.fragment_number += 1


class OutputLogHandler(EndpointLogHandler):
    """
    Implementation of EndpointLogHandler that writes logs to the output
    endpoint in Testflinger server.
    """

    def write_to_endpoint(self, data: LogEndpointInput):
        self.client.post_log(self.job_id, data, LogType.STANDARD_OUTPUT)


class SerialLogHandler(EndpointLogHandler):
    """
    Implementation of EndpointLogHandler that writes logs to the serial
    endpoint in Testflinger server.
    """

    def write_to_endpoint(self, data: LogEndpointInput):
        self.client.post_log(self.job_id, data, LogType.SERIAL_OUTPUT)
