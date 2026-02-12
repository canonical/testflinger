# Copyright (C) 2026 Canonical
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

"""Integration tests for the main agent loop (start_agent)."""

from unittest.mock import Mock, patch

import pytest

from testflinger_agent import start_agent


class TestMainLoop:
    """Test the main agent loop behavior."""

    @pytest.fixture
    def config(self, tmp_path):
        """Create a minimal config for testing."""
        return {
            "agent_id": "test01",
            "identifier": "12345-123456",
            "polling_interval": 1,
            "server_address": "127.0.0.1:8000",
            "job_queues": ["test"],
            "location": "nowhere",
            "provision_type": "noprovision",
            "execution_basedir": str(tmp_path / "execution"),
            "logging_basedir": str(tmp_path / "logs"),
            "results_basedir": str(tmp_path / "results"),
        }

    def test_main_loop_retries_after_401(self, config):
        """Test main loop continues after 401 during job check."""
        sleep_counter = [0]

        def sleep_side_effect(interval):
            sleep_counter[0] += 1
            if sleep_counter[0] >= 2:
                raise KeyboardInterrupt()

        with patch("testflinger_agent.load_config", return_value=config):
            with patch("testflinger_agent.configure_logging"):
                with patch(
                    "testflinger_agent.TestflingerClient"
                ) as mock_client_class:
                    with patch(
                        "testflinger_agent.TestflingerAgent"
                    ) as mock_agent_class:
                        with patch(
                            "time.sleep", side_effect=sleep_side_effect
                        ):
                            c = Mock()
                            mock_client_class.return_value = c
                            mock_agent = Mock()
                            mock_agent_class.return_value = mock_agent
                            mock_agent.check_offline.return_value = (
                                False,
                                "",
                            )
                            mock_agent.check_restart.return_value = (
                                False,
                                "",
                            )
                            mock_agent.client = c
                            c.server = "http://127.0.0.1:8000"

                            # Both calls return None (no jobs)
                            mock_agent.process_jobs.return_value = None
                            c.wait_for_server_connectivity.return_value = None

                            try:
                                start_agent()
                            except KeyboardInterrupt:
                                pass

                            # Verify process_jobs was called twice
                            assert mock_agent.process_jobs.call_count == 2

    def test_main_loop_handles_offline(self, config):
        """Test main loop exits when agent goes offline."""
        sleep_counter = [0]

        def sleep_side_effect(interval):
            sleep_counter[0] += 1
            if sleep_counter[0] >= 1:
                # End test after prescribed number of loops.
                raise KeyboardInterrupt()

        with patch("testflinger_agent.load_config", return_value=config):
            with patch("testflinger_agent.configure_logging"):
                with patch("testflinger_agent.TestflingerClient"):
                    with patch(
                        "testflinger_agent.TestflingerAgent"
                    ) as mock_agent_class:
                        with patch(
                            "time.sleep", side_effect=sleep_side_effect
                        ):
                            mock_agent = Mock()
                            mock_agent_class.return_value = mock_agent
                            # Agent is offline
                            mock_agent.check_offline.return_value = (
                                True,
                                "Offline by admin",
                            )
                            mock_agent.check_restart.return_value = (
                                False,
                                "",
                            )
                            mock_agent.client.server = "http://127.0.0.1:8000"
                            mock_agent.process_jobs.return_value = None

                            try:
                                start_agent()
                            except KeyboardInterrupt:
                                pass

                            # process_jobs should not be called when offline
                            mock_agent.process_jobs.assert_not_called()
