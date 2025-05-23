# Copyright (C) 2024 Canonical
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

import time

from testflinger_common.enums import TestEvent

from testflinger_agent.client import TestflingerClient
from testflinger_agent.stop_condition_checkers import (
    GlobalTimeoutChecker,
    JobCancelledChecker,
    OutputTimeoutChecker,
)


class TestStopConditionCheckers:
    def test_job_cancelled_checker(self, mocker):
        """Test that the job cancelled checker detects cancelled state."""
        client = TestflingerClient({"server_address": "http://localhost"})
        checker = JobCancelledChecker(client, "job_id")

        # Nothing should happen if the job is not cancelled
        mocker.patch.object(client, "check_job_state", return_value="test")
        assert checker() == (None, "")

        # If the job is cancelled, the checker should return a message
        mocker.patch.object(
            client, "check_job_state", return_value="cancelled"
        )
        stop_event, detail = checker()
        assert "Job cancellation was requested, exiting." in detail
        assert stop_event == TestEvent.CANCELLED

    def test_global_timeout_checker(self):
        """Test that the global timeout checker works as expected."""
        checker = GlobalTimeoutChecker(0.5)
        assert checker() == (None, "")
        time.sleep(0.6)
        stop_event, detail = checker()
        assert "ERROR: Global timeout reached! (0.5s)" in detail
        assert stop_event == TestEvent.GLOBAL_TIMEOUT

    def test_output_timeout_checker(self):
        """Test that the output timeout checker works as expected."""
        checker = OutputTimeoutChecker(0.5)
        assert checker() == (None, "")
        time.sleep(0.6)
        stop_event, detail = checker()
        assert "ERROR: Output timeout reached! (0.5s)" in detail
        assert stop_event == TestEvent.OUTPUT_TIMEOUT

    def test_output_timeout_update(self):
        """
        Test that the output timeout checker doesn't get triggered when we
        keep updating the last output time.
        """
        checker = OutputTimeoutChecker(0.3)
        for _ in range(5):
            time.sleep(0.1)
            checker.update()
            assert checker() == (None, "")
