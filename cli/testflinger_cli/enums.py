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
Job State and Test Phase Enums.
Duplicated from testflinger_common.
"""

from strenum import StrEnum


class TestPhase(StrEnum):
    """Enum of Test Phases."""

    __test__ = False
    """Prevents pytest from trying to run this class as a test."""

    SETUP = "setup"
    PROVISION = "provision"
    FIRMWARE_UPDATE = "firmware_update"
    TEST = "test"
    ALLOCATE = "allocate"
    RESERVE = "reserve"
    CLEANUP = "cleanup"


class LogType(StrEnum):
    """
    Enum of different output types
    STANDARD_OUTPUT - Agent Standard Output
    SERIAL_OUTPUT - Agent Serial Log Output.
    """

    STANDARD_OUTPUT = "output"
    SERIAL_OUTPUT = "serial"
