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

from unittest.mock import patch

import pytest
import voluptuous
import yaml

from testflinger_agent import cmd


@patch("sys.exit")
@patch("testflinger_agent.cmd.start_agent")
def test_agent_start_valid_config(mock_start_agent, mock_exit):
    """Test entrypoint does not call exit on valid configuration."""
    cmd.main()
    mock_exit.assert_not_called()


@pytest.mark.parametrize(
    "exception",
    [
        OSError("Address already in use"),
        yaml.YAMLError("Invalid YAML"),
        voluptuous.MultipleInvalid("Invalid config"),
    ],
)
@patch("sys.exit")
@patch("testflinger_agent.cmd.start_agent")
def test_agent_start_exceptions_on_invalid_config(
    mock_start_agent, mock_exit, exception
):
    """Test entrypoint exits with code 1 on known configuration errors."""
    mock_start_agent.side_effect = exception
    cmd.main()
    mock_exit.assert_called_once_with(1)


@patch("testflinger_agent.cmd.start_agent", side_effect=KeyboardInterrupt)
@patch("sys.exit")
def test_agent_start_keyboard_interrupt(mock_exit, mock_start_agent):
    """Test entrypoint handles KeyboardInterrupt gracefully."""
    cmd.main()
    mock_exit.assert_called_once_with(0)


@patch(
    "testflinger_agent.cmd.start_agent",
    side_effect=Exception("Unexpected error"),
)
@patch("sys.exit")
def test_agent_start_unspecified_exception(mock_exit, mock_start_agent):
    """Test entrypoint does not call explicit exit for unknown exceptions."""
    cmd.main()
    mock_exit.assert_not_called()
