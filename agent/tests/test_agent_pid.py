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
# along with this program.  If not, see <http://www.gnu.org/licenses/>

import os
import signal
from pathlib import Path
from unittest.mock import patch

import pytest

from testflinger_agent import agent_pid


@pytest.fixture
def pid_file(config):
    """Fixture for a PID file path."""
    return Path(config["logging_basedir"]) / f"{config['agent_id']}.pid"


def test_agent_write_pid(pid_file):
    """Test that agent PID file is written with the current PID on startup."""
    agent_pid.write(pid_file)
    assert pid_file.read_text() == str(os.getpid())


@patch("pathlib.Path.write_text", side_effect=OSError("Disk full"))
def test_agent_write_os_error(mock_write_text, pid_file, caplog):
    """Test that agent PID file write handles OSError."""
    with pytest.raises(OSError, match="Disk full"):
        agent_pid.write(pid_file)
    assert "Failed to write PID file" in caplog.text


def test_agent_cleanup_pid_file(pid_file):
    """Test that PID file is removed on cleanup."""
    agent_pid.write(pid_file)

    agent_pid._cleanup(pid_file)
    assert not pid_file.exists()


def test_agent_not_cleanup_foreign_pid(pid_file):
    """Test that PID file belonging to another PID is not removed."""
    pid_file.write_text("99999999")

    agent_pid._cleanup(pid_file)
    assert pid_file.exists()


@patch("pathlib.Path.unlink", side_effect=OSError("Permission denied"))
def test_agent_cleanup_os_error(mock_unlink, pid_file, caplog):
    """Test that agent PID file cleanup logs OSError without raising."""
    agent_pid.write(pid_file)

    # Only log the error as this doesn't re-raise
    agent_pid._cleanup(pid_file)
    assert "Failed to remove PID file" in caplog.text


@patch("pathlib.Path.read_text", side_effect=OSError("Permission denied"))
def test_agent_cleanup_read_os_error(mock_read_text, pid_file, caplog):
    """Test that OSError when reading PID file during cleanup is logged."""
    pid_file.write_text(str(os.getpid()))

    # Only log the error as this doesn't re-raise
    agent_pid._cleanup(pid_file)
    assert "Failed to check PID file" in caplog.text


@patch("pathlib.Path.unlink")
def test_agent_terminate_stale_no_pid_file(mock_unlink, pid_file):
    """Test terminate_stale early return if no PID file exists."""
    agent_pid.terminate_stale(pid_file, "dummy_config_path")
    assert not pid_file.exists()
    mock_unlink.assert_not_called()


@patch("os.kill")
def test_agent_terminate_stale_clean_old_pid_file(mock_kill, pid_file):
    """Test stale PID file without any matching process is cleaned up."""
    pid_file.write_text("99999999")
    agent_pid.terminate_stale(pid_file, "testflinger-agent.conf")
    assert not pid_file.exists()
    mock_kill.assert_not_called()


@patch("os.kill")
def test_agent_terminate_stale_malformed_pid(mock_kill, pid_file):
    """Test that malformed PID file is cleaned up."""
    pid_file.write_text("not_a_pid")
    agent_pid.terminate_stale(pid_file, "testflinger-agent.conf")
    assert not pid_file.exists()
    mock_kill.assert_not_called()


@patch(
    "pathlib.Path.read_bytes",
    return_value=b"some-other-program\x00--flag",
)
@patch("os.kill")
def test_agent_terminate_stale_mismatched_cmdline(
    mock_killed, mock_read_bytes, pid_file, caplog
):
    """Test that PID file is cleaned up when cmdline doesn't match."""
    pid_file.write_text(str(os.getpid()))
    agent_pid.terminate_stale(pid_file, "testflinger-agent.conf")
    assert not pid_file.exists()
    assert "does not match this agent" in caplog.text
    mock_killed.assert_not_called()


@patch("os.kill")
@patch(
    "pathlib.Path.read_bytes",
    return_value=b"testflinger-agent\x00--config\x00testflinger-agent.conf",
)
def test_agent_terminate_stale_kills_orphan(
    mock_read_bytes, mock_kill, pid_file
):
    """Test that a matching orphan process is SIGKILLed."""
    pid_file.write_text(str(os.getpid()))
    agent_pid.terminate_stale(pid_file, "testflinger-agent.conf")
    mock_kill.assert_called_once_with(os.getpid(), signal.SIGKILL)


@patch("os.kill", side_effect=ProcessLookupError)
@patch(
    "pathlib.Path.read_bytes",
    return_value=b"testflinger-agent\x00--config\x00testflinger-agent.conf",
)
def test_agent_terminate_stale_process_already_dead(
    mock_read_bytes, mock_kill, pid_file
):
    """Test that ProcessLookupError after SIGKILL is silently ignored."""
    pid_file.write_text(str(os.getpid()))
    # must not raise
    agent_pid.terminate_stale(pid_file, "testflinger-agent.conf")
    mock_kill.assert_called_once()
