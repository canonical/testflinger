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


class RestartHandler:
    """Handler to determine if restart is needed at any stage of the agent."""

    def __init__(self):
        """Initialize handler with default values."""
        self.needs_restart = False
        self.comment = ""

    def update(self, restart: bool, comment: str) -> None:
        """Update the attributes of the class if needed.

        :param restart: Flag to set if agent needs restarting.
        :param comment: Reason for requesting agent restart.
        """
        if restart and not self.needs_restart:
            self.needs_restart = True
            self.comment = comment
        elif self.needs_restart and comment:
            self.comment = f"Restart Pending: {comment}"

    def marked_for_restart(self) -> bool:
        """Indicate the current restart state of the restart handler.

        :return: True if a restart is neeeded, False otherwise.
        """
        return self.needs_restart

    def get_comment(self) -> str:
        """Retrieve the comment from the restart handler.

        :return: Preserved comment if an agent was set to restart.
        """
        return self.comment
