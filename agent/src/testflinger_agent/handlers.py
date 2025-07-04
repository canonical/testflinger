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
        self.needs_restart = False
        self.needs_offline = False
        self.comment = ""

    def update(
        self, comment: str, restart: bool = False, offline: bool = False
    ) -> None:
        """Update the attributes of the class if needed.

        :param restart: Flag to set if agent needs restarting.
        :param offline: Flag to set if agent needs offlining.
        :param comment: Reason for requesting agent status change.
        """
        if restart and not self.needs_restart:
            self.needs_restart = True
            if not self.needs_offline:
                self.comment = comment
        if offline and not self.needs_offline:
            self.needs_offline = True
            self.comment = comment

    def marked_for_restart(self) -> bool:
        """Indicate the current restart state of the restart handler.

        :return: True if a restart is neeeded, False otherwise.
        """
        return self.needs_restart

    def marked_for_offline(self) -> bool:
        """Indicate the current offline state of the offline handler.

        :return: True if a offline is neeeded, False otherwise.
        """
        return self.needs_offline

    def get_comment(self) -> str:
        """Retrieve the comment from the status handler.

        :return: Preserved comment if an agent status was modified.
        """
        return self.comment
