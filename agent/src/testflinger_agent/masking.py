# Copyright (C) 2025 Canonical
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

"""
Text masking for sensitive information.

This module provides functionality to mask sensitive information in text.
Each matched pattern is replaced with a deterministic hash, ensuring that
the same sensitive information is always replaced by the same mask.
"""

import hashlib
import re
from typing import List, Optional


class Masker:
    """
    A class for masking sensitive information in text.

    Example:
    ```
    >>> masker = Masker([r"\d{3}-\d{2}-\d{4}"], hash_length=6)
    >>> masker.apply("SSN: 123-45-6789")
    'SSN: **01a546**'
    ```
    """  # noqa: D301, W605 due to regular expression in docstring

    def __init__(self, patterns: List[str], hash_length: Optional[int] = None):
        # join all patterns into a single combined pattern and compile it
        combined = self.combine(pattern for pattern in patterns if pattern)
        if not combined:
            raise ValueError("Empty combined pattern")
        self.pattern = re.compile(combined)
        # the length of the hash to be used for masking
        # (a value of `None` results in the full hash length)
        self.hash_length = hash_length

    @staticmethod
    def combine(patterns: List[str]) -> str:
        """Return a single disjunctive regular expression from `patterns`."""
        return "|".join(f"({pattern})" for pattern in patterns)

    @staticmethod
    def hash(text: str) -> str:
        """Return a hash for `text`."""
        return hashlib.sha256(text.encode()).hexdigest()

    def mask(self, match: re.Match) -> str:
        """Return a string with a mask applied on a pattern `match`."""
        return f"**{self.hash(match.group())[: self.hash_length]}**"

    def apply(self, text: str) -> str:
        """Return a string with all pattern matches in `text` masked."""
        return self.pattern.sub(self.mask, text)
