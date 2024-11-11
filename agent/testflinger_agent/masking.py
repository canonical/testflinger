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
        >>> masker = Masker(['\\d{3}-\\d{2}-\\d{4}'], hash_length=6)
        >>> masker.apply("SSN: 123-45-6789")
        'SSN: **01a546**'
    """

    def __init__(self, patterns: List[str], hash_length: Optional[int] = None):
        # join all patterns into a single combined pattern and compile it
        combined = "|".join(f"({pattern})" for pattern in patterns)
        self.pattern = re.compile(combined)
        # the length of the hash to be used for masking
        # (a value of `None` results in the full hash length)
        self.hash_length = hash_length

    def hash(self, text: str) -> str:
        """Return a hash of appropriate length for the giver `text`"""
        return hashlib.sha256(text.encode()).hexdigest()[: self.hash_length]

    def mask(self, match: re.Match) -> str:
        """Return a string with a mask applied on a pattern `match`"""
        return f"**{self.hash(match.group())}**"

    def apply(self, text: str) -> str:
        """Return a string with all pattern matches in `text` masked"""
        return self.pattern.sub(self.mask, text)
