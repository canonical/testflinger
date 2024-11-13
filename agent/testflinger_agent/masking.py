"""
Text masking for sensitive information.

This module provides functionality to mask sensitive information in text.
Each matched pattern is replaced with a deterministic hash, ensuring that
the same sensitive information is always replaced by the same mask.
"""

import hashlib
import os
import re
from typing import List, Optional


class Masker:
    """
    A class for masking sensitive information in text.

    Example:
        >>> masker = Masker(['\\d{3}-\\d{2}-\\d{4}'], hash_length=6)
        >>> masker.apply("SSN: 123-45-6789")
        'SSN: **01a546**'
    """

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
        """Return a single disjunctive regular expression from `patterns`"""
        return "|".join(f"({pattern})" for pattern in patterns)

    @staticmethod
    def hash(text: str) -> str:
        """Return a hash for `text`"""
        return hashlib.sha256(text.encode()).hexdigest()

    def mask(self, match: re.Match) -> str:
        """Return a string with a mask applied on a pattern `match`"""
        return f"**{self.hash(match.group())[:self.hash_length]}**"

    def apply(self, text: str) -> str:
        """Return a string with all pattern matches in `text` masked"""
        return self.pattern.sub(self.mask, text)
