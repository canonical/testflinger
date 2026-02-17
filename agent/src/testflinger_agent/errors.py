# Copyright (C) 2016 Canonical
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


class TFServerError(Exception):
    def __init__(self, m):
        """Initialize TFServerError."""
        self.code = m
        self.message = "HTTP Status: {}".format(m)

    def __str__(self):
        """Return a string with the the error message."""
        return self.message


class InvalidTokenError(Exception):
    """Base class for errors related to authentication and authorization."""
