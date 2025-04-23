# Copyright (C) 2024 Canonical
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
Custom JSON providers for when jsonify() doesn't do what we want
"""

from datetime import datetime
from flask.json.provider import DefaultJSONProvider


class ISODatetimeProvider(DefaultJSONProvider):  # pylint: disable=too-few-public-methods
    """Return datetime objects as RFC3339/ISO8601 strings with a 'Z' suffix."""

    def default(self, obj):
        """Encode datetime objects as ISO8601, no effect on other types."""
        if isinstance(obj, datetime):
            return obj.isoformat(timespec="seconds") + "Z"
        return super().default(obj)
