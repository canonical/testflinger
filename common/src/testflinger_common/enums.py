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
Job State and Test Phase Enums
"""

from strenum import StrEnum


class JobState(StrEnum):
    WAITING = "waiting"
    SETUP = "setup"
    PROVISION = "provision"
    FIRMWARE_UPDATE = "firmware_update"
    TEST = "test"
    ALLOCATE = "allocate"
    ALLOCATED = "allocated"
    RESERVE = "reserve"
    CLEANUP = "cleanup"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class TestPhase(StrEnum):
    __test__ = False
    """Prevents pytest from trying to run this class as a test."""

    SETUP = "setup"
    PROVISION = "provision"
    FIRMWARE_UPDATE = "firmware_update"
    TEST = "test"
    ALLOCATE = "allocate"
    RESERVE = "reserve"
    CLEANUP = "cleanup"


class TestEvent(StrEnum):
    __test__ = False
    """Prevents pytest from trying to run this class as a test."""

    SETUP_START = "setup_start"
    PROVISION_START = "provision_start"
    FIRMWARE_UPDATE_START = "firmware_update_start"
    TEST_START = "test_start"
    ALLOCATE_START = "allocate_start"
    RESERVE_START = "reserve_start"
    CLEANUP_START = "cleanup_start"

    SETUP_SUCCESS = "setup_success"
    PROVISION_SUCCESS = "provision_success"
    FIRMWARE_UPDATE_SUCCESS = "firmware_update_success"
    TEST_SUCCESS = "test_success"
    ALLOCATE_SUCCESS = "allocate_success"
    RESERVE_SUCCESS = "reserve_success"
    CLEANUP_SUCCESS = "cleanup_success"

    SETUP_FAIL = "setup_fail"
    PROVISION_FAIL = "provision_fail"
    FIRMWARE_UPDATE_FAIL = "firmware_update_fail"
    TEST_FAIL = "test_fail"
    ALLOCATE_FAIL = "allocate_fail"
    RESERVE_FAIL = "reserve_fail"
    CLEANUP_FAIL = "cleanup_fail"

    CANCELLED = "cancelled"
    GLOBAL_TIMEOUT = "global_timeout"
    OUTPUT_TIMEOUT = "output_timeout"
    RECOVERY_FAIL = "recovery_fail"

    NORMAL_EXIT = "normal_exit"
    JOB_START = "job_start"
    JOB_END = "job_end"


class AgentState(StrEnum):
    WAITING = "waiting"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"
    RESTART = "restart"
