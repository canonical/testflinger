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
#
"""Helpers for the Testflinger API."""

import posixpath
import re
from urllib.parse import urlparse

PERCENT_ENCODED_OCTET = re.compile(r"%[0-9a-fA-F]{2}")


def is_url_valid(base_url: str, target_url: str) -> bool:
    """Validate target_url against base_url.

    This evaluates:
    1. Scheme and netloc of target_url must match base_url.
    2. There are no percent-encoded octets in the target_url path.
    3. Ensure target URL has a path
    4. Ensure target_url is not identical to base_url after normalization.
    5. After normalization, target_url must be a child path of base_url.

    :param base_url: The base URL to compare against
    :param target_url: The target URL to validate
    :return: True if the target URL is valid, False otherwise
    """
    parsed_base = urlparse(base_url)
    parsed_target = urlparse(target_url)

    # 1. Validate scheme and netloc
    if (
        parsed_base.scheme != parsed_target.scheme
        or parsed_base.netloc != parsed_target.netloc
    ):
        return False

    # 2. Reject encoded octets in path for fixed-format URLs.
    target_path_raw = parsed_target.path
    if PERCENT_ENCODED_OCTET.search(target_path_raw):
        return False

    # 3. Ensure target URL has a path
    if not target_path_raw:
        return False

    # 4. Ensure target URL is not identical to base URL after normalization
    normalized_base_path = posixpath.normpath(parsed_base.path)
    normalized_target_path = posixpath.normpath(target_path_raw)
    if normalized_target_path == normalized_base_path:
        return False

    # 5. Ensure target URL is a child path of base URL after normalization
    base_prefix = f"{normalized_base_path.rstrip('/')}/"
    if not normalized_target_path.startswith(base_prefix):
        return False

    return True
