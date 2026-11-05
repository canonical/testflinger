# Copyright (C) 2026 Canonical
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

"""Exceptions related to the Jira integration."""


class JiraError(Exception):
    """Base class for errors related to the Jira integration."""


class JiraConfigError(JiraError):
    """Raised when the Jira credentials are missing."""


class JiraRequestError(JiraError):
    """Raised when Jira rejects a request or cannot be reached."""

    def __init__(self, status: int | None, messages: list[str]):
        """Store the HTTP status and the error messages from Jira."""
        super().__init__(status, messages)
        self.status = status
        self.messages = messages

    def __str__(self) -> str:
        """Return a readable description of the failure."""
        message = self.messages[0] if self.messages else "Unknown error"
        return f"[{self.status}] Jira request failed: {message}"
