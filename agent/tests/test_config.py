# Copyright (C) 2016 Canonical
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

import json

import pytest
import voluptuous

import testflinger_agent

BAD_CONFIG = """
badkey: foo
"""


def test_config_good(tmp_path, config):
    """Test that a valid config file is loaded correctly."""
    configfile = tmp_path / "config.yaml"
    with configfile.open("w") as f:
        json.dump(config, f)
    agent_config = testflinger_agent.load_config(configfile)
    assert "test01" == agent_config.get("agent_id")


def test_config_bad(tmp_path):
    """Test that an invalid config file raises an schema error."""
    configfile = tmp_path / "config.yaml"
    with configfile.open("w") as f:
        f.write(BAD_CONFIG)
    with pytest.raises(
        voluptuous.error.MultipleInvalid,
    ):
        testflinger_agent.load_config(configfile)
