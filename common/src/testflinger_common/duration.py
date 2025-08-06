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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Duration parsing utilities for Testflinger.

This module provides utilities to parse duration strings in human-readable
formats (like '30m', '5h', '4d') into seconds, similar to the sleep command.
"""

import re
from typing import Union


class DurationParseError(ValueError):
    """Raised when a duration string cannot be parsed."""

    pass


def parse_duration(duration: Union[str, int]) -> int:
    """Parse a duration string or integer into seconds.

    Supports the following formats:
    - Plain integers (interpreted as seconds): 3600
    - Duration strings with suffixes:
      - 's' or 'sec' for seconds: '30s', '30sec'
      - 'm' or 'min' for minutes: '30m', '30min'
      - 'h' or 'hour' for hours: '5h', '5hour'
      - 'd' or 'day' for days: '4d', '4day'

    Multiple units can be combined: '1h30m', '2d5h30m'

    Args:
        duration: Duration as string or integer

    Returns:
        Duration in seconds as integer

    Raises:
        DurationParseError: If the duration string is invalid

    Examples:
        >>> parse_duration(3600)
        3600
        >>> parse_duration('30m')
        1800
        >>> parse_duration('5h')
        18000
        >>> parse_duration('4d')
        345600
        >>> parse_duration('1h30m')
        5400
        >>> parse_duration('2d5h30m')
        192600
    """
    if isinstance(duration, int):
        if duration < 0:
            raise DurationParseError("Duration cannot be negative")
        return duration

    if not isinstance(duration, str):
        raise DurationParseError(
            f"Duration must be string or int, got {type(duration)}"
        )

    duration = duration.strip()
    if not duration:
        raise DurationParseError("Duration cannot be empty")

    # Try parsing as plain integer first
    try:
        value = int(duration)
        if value < 0:
            raise DurationParseError("Duration cannot be negative")
        return value
    except ValueError:
        pass

    # Check for negative numbers in duration strings
    if duration.strip().startswith("-"):
        raise DurationParseError("Duration cannot be negative")

    # Parse duration string with units
    # Pattern matches: number followed by optional unit
    # Units: s/sec, m/min, h/hour, d/day (case insensitive)
    # Order matters - longer forms first to avoid partial matches
    pattern = r"(\d+)\s*(secs?|mins?|hours?|days?|sec|min|hour|day|s|m|h|d)"
    matches = re.findall(pattern, duration.lower())

    if not matches:
        raise DurationParseError(f"Invalid duration format: '{duration}'")

    # Check if the entire string was consumed by matches
    # Reconstruct what should have been matched and compare
    reconstructed = ""
    for num, unit in matches:
        reconstructed += f"{num}{unit}"

    # Remove all whitespace for comparison
    normalized_input = re.sub(r"\s+", "", duration.lower())

    if normalized_input != reconstructed:
        raise DurationParseError(f"Invalid duration format: '{duration}'")

    total_seconds = 0
    unit_multipliers = {
        "s": 1,
        "sec": 1,
        "secs": 1,
        "m": 60,
        "min": 60,
        "mins": 60,
        "h": 3600,
        "hour": 3600,
        "hours": 3600,
        "d": 86400,
        "day": 86400,
        "days": 86400,
    }

    for num_str, unit in matches:
        num = int(num_str)
        if num < 0:
            raise DurationParseError("Duration components cannot be negative")

        multiplier = unit_multipliers[unit]
        total_seconds += num * multiplier

    return total_seconds


def format_duration(seconds: int) -> str:
    """Format seconds into a human-readable duration string.

    Args:
        seconds: Duration in seconds

    Returns:
        Human-readable duration string

    Examples:
        >>> format_duration(3600)
        '1h'
        >>> format_duration(1800)
        '30m'
        >>> format_duration(5400)
        '1h30m'
        >>> format_duration(345600)
        '4d'
    """
    if seconds < 0:
        raise ValueError("Duration cannot be negative")

    if seconds == 0:
        return "0s"

    parts = []

    # Days
    if seconds >= 86400:
        days = seconds // 86400
        parts.append(f"{days}d")
        seconds %= 86400

    # Hours
    if seconds >= 3600:
        hours = seconds // 3600
        parts.append(f"{hours}h")
        seconds %= 3600

    # Minutes
    if seconds >= 60:
        minutes = seconds // 60
        parts.append(f"{minutes}m")
        seconds %= 60

    # Seconds
    if seconds > 0:
        parts.append(f"{seconds}s")

    return "".join(parts)
