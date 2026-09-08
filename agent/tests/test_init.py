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

import fcntl
import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

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
    @patch("time.sleep", side_effect=[None, KeyboardInterrupt()])
    def test_main_loop_continues_polling_on_empty_queue(
        self,
        mock_sleep,
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
        mock_agent.check_offline.return_value = (False, "")
        mock_agent.process_jobs.return_value = None

        try:
            start_agent()
        except KeyboardInterrupt:
            pass

        # Verify process_jobs was called twice
        assert mock_agent.process_jobs.call_count == 2

    @patch("testflinger_agent.load_config")
    @patch("testflinger_agent.configure_logging")
    @patch("testflinger_agent.TestflingerClient")
    @patch("testflinger_agent.TestflingerAgent")
    @patch("time.sleep", side_effect=[KeyboardInterrupt()])
    def test_main_loop_skips_processing_when_offline(
        self,
        mock_sleep,
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
        mock_agent.check_offline.return_value = (True, "Offline by admin")
        mock_agent.process_jobs.return_value = None

        try:
            start_agent()
        except KeyboardInterrupt:
            pass

        # process_jobs should not be called when offline
        mock_agent.process_jobs.assert_not_called()

    @patch("testflinger_agent.load_config")
    @patch("testflinger_agent.configure_logging")
    @patch("testflinger_agent._acquire_venv_lock")
    @patch("testflinger_agent.TestflingerClient")
    @patch("testflinger_agent.TestflingerAgent")
    @patch("time.sleep", side_effect=[KeyboardInterrupt()])
    def test_main_loop_acquires_venv_lock_at_startup(
        self,
        mock_sleep,
        mock_agent_class,
        mock_client_class,
        mock_acquire_lock,
        mock_configure_logging,
        mock_load_config,
        config,
    ):
        """Test start_agent acquires the venv lock once during startup."""
        mock_load_config.return_value = config
        mock_agent = Mock()
        mock_agent_class.return_value = mock_agent
        mock_agent.check_offline.return_value = (False, "")
        mock_agent.process_jobs.return_value = None

        try:
            start_agent()
        except KeyboardInterrupt:
            pass

        mock_acquire_lock.assert_called_once()


class TestAcquireVenvLock:
    """Test the agent-held venv lock acquired at startup."""

    def test_acquires_shared_lock_on_resolved_venv(
        self, tmp_path, monkeypatch
    ):
        """Test the lock is acquired against sys.executable's resolved venv."""
        venv_root = tmp_path / "testflinger-venv-20260824_103045"
        (venv_root / "bin").mkdir(parents=True)
        python_path = venv_root / "bin" / "python3"
        python_path.touch()
        lock_path = venv_root / testflinger_agent.VENV_LOCK_FILENAME
        lock_path.touch()

        monkeypatch.setattr("sys.executable", str(python_path))

        file_descriptor = testflinger_agent._acquire_venv_lock()
        try:
            assert file_descriptor is not None

            # A second, independent exclusive-lock attempt must fail while
            # the shared lock above is still held.
            probe_fd = os.open(lock_path, os.O_RDWR)
            try:
                with pytest.raises(OSError):
                    fcntl.flock(probe_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            finally:
                os.close(probe_fd)
        finally:
            if file_descriptor is not None:
                os.close(file_descriptor)

    def test_returns_none_when_lock_file_missing(self, tmp_path, monkeypatch):
        """Test lock acquisition is best-effort: missing lock file is ok."""
        venv_root = tmp_path / "testflinger-venv-20260824_103045"
        (venv_root / "bin").mkdir(parents=True)
        python_path = venv_root / "bin" / "python3"
        python_path.touch()
        # No .venv.lock file created - simulates a venv predating this
        # feature, or the charm's create_virtualenv() lock-file fix.

        monkeypatch.setattr("sys.executable", str(python_path))

        assert testflinger_agent._acquire_venv_lock() is None
