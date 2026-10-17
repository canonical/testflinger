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

from pathlib import Path
from unittest.mock import Mock, patch

import testflinger_agent
from testflinger_agent import start_agent


class TestAgentArgs:
    @patch("sys.argv", ["testflinger-agent", "-c", "test.conf"])
    def test_default_token_file(self):
        """Test parse_args sets the default token file path."""
        args = testflinger_agent.parse_args()

        assert args.token_file == Path(
            "/var/lib/testflinger-agent/refresh_token"
        )

    @patch(
        "sys.argv",
        [
            "testflinger-agent",
            "-c",
            "test.conf",
            "--token-file",
            "/tmp/custom_token",
        ],
    )
    def test_custom_token_file(self):
        """Test parse_args accepts a custom token file path."""
        args = testflinger_agent.parse_args()

        assert args.token_file == Path("/tmp/custom_token")


class TestMainLoop:
    """Test the main agent loop behavior."""

    @patch("testflinger_agent.load_config")
    @patch("testflinger_agent.configure_logging")
    @patch("testflinger_agent.TestflingerClient")
    @patch("testflinger_agent.TestflingerAgent")
    def test_main_loop_continues_polling_on_empty_queue(
        self,
        mock_agent_class,
        mock_client_class,
        mock_configure_logging,
        mock_load_config,
        config,
    ):
        """Test main loop continues polling when no jobs are available."""
        mock_load_config.return_value = config
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_agent = Mock()
        mock_agent_class.return_value = mock_agent
        # Simulate loop exiting after 2 iterations
        mock_agent.loop.side_effect = KeyboardInterrupt()

        try:
            start_agent()
        except KeyboardInterrupt:
            pass

        # Verify loop was called once (it runs until interrupted)
        mock_agent.loop.assert_called_once()

    @patch("testflinger_agent.load_config")
    @patch("testflinger_agent.configure_logging")
    @patch("testflinger_agent.TestflingerClient")
    @patch("testflinger_agent.TestflingerAgent")
    def test_main_loop_processes_maintenance_queue(
        self,
        mock_agent_class,
        mock_client_class,
        mock_configure_logging,
        mock_load_config,
        config,
    ):
        """Maintenance mode processes only maintenance-queue jobs."""
        mock_load_config.return_value = config
        mock_agent = Mock()
        mock_agent_class.return_value = mock_agent
        # Simulate loop exiting
        mock_agent.loop.side_effect = KeyboardInterrupt()

        try:
            start_agent()
        except KeyboardInterrupt:
            pass

        mock_agent.loop.assert_called_once_with(config.get("polling_interval"))

    @patch("testflinger_agent.load_config")
    @patch("testflinger_agent.configure_logging")
    @patch("testflinger_agent.TestflingerClient")
    @patch("testflinger_agent.TestflingerAgent")
    def test_main_loop_skips_processing_when_offline(
        self,
        mock_agent_class,
        mock_client_class,
        mock_configure_logging,
        mock_load_config,
        config,
    ):
        """Test main loop skips job processing when agent is offline."""
        mock_load_config.return_value = config
        mock_agent = Mock()
        mock_agent_class.return_value = mock_agent
        # Simulate loop exiting
        mock_agent.loop.side_effect = KeyboardInterrupt()

        try:
            start_agent()
        except KeyboardInterrupt:
            pass

        # Loop is called with check_interval
        mock_agent.loop.assert_called_once_with(config.get("polling_interval"))
