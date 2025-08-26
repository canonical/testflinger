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

from datetime import UTC, datetime

from .client import TestflingerClient


class LiveOutputHandler:
    def __init__(self, client: TestflingerClient, job_id: str):
        self.client = client
        self.job_id = job_id

    def __call__(self, data: str):
        self.client.post_live_output(self.job_id, data)


class LogUpdateHandler:
    def __init__(self, log_file: str):
        self.log_file = log_file

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

class AgentHeartbeatHandler:
    """Handler to determine if agent needs to send a heartbeat signal."""

    def __init__(self, client: TestflingerClient, heartbeat_frequency: int):
        """Initialize handler with default values."""
        self.client = client
        self.heartbeat_frequency = heartbeat_frequency
        self._agent_data = {}
        # Agent sent heartbeat upon initialization or restart
        self._last_heartbeat = datetime.now(UTC)

    def update(self, agent_data: dict):
        """Update agent_data retrieved from server.

        :param agent_data: Agent information retrieved from server.
        """
        if agent_data:
            self._agent_data = agent_data
            self._refresh_last_heartbeat()
            self._send_heartbeat()

    def _refresh_last_heartbeat(self) -> None:
        """Update heartbeat from agent_data.

        :param agent_data: All agent information retrieved from server.
        """
        if "updated_at" in self._agent_data:
            # Parse ISO format timestamp
            timestamp = self._agent_data["updated_at"]
            self._last_heartbeat = datetime.fromisoformat(
                timestamp.replace("Z", "+00:00")
            )

    def _send_heartbeat(self) -> None:
        """Send a heartbeat to the server if needed.

        Heartbeat signal is current agent status and comment.
        """
        if self.is_heartbeat_required():
            comment = self._agent_data.get("comment", "")
            if "state" in self._agent_data:
                agent_state = self._agent_data["state"]
                self.client.post_agent_data(
                    {"state": agent_state, "comment": comment}
                )

    def is_heartbeat_required(self) -> bool:
        """Determine if heartbeat is required to send to server.

        :return: True or False if heartbeat is required
        """
        time_delta = datetime.now(UTC) - self._last_heartbeat
        # Heartbeat is required at least once per heartbeat frequency
        if time_delta.days >= self.heartbeat_frequency:
            return True
        return False
