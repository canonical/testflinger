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
"""Helpers for charm unit tests."""

import base64
import os


def generate_b64_key(bytes_n: int = 96) -> str:
    """Generate a random base64-encoded key string for testing.

    :param bytes_n: Number of random bytes to generate before encoding.
    :return: Base64-encoded string of the random bytes.
    """
    return base64.b64encode(os.urandom(bytes_n)).decode()
