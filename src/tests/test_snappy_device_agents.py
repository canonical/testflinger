# Copyright (C) 2019 Canonical
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

import snappy_device_agents


class TestCommandsTemplate:
    """Tests to ensure test_cmds templating works properly"""

    def test_known_config_items(self):
        """Known config items should fill in the expected value"""
        cmds = "test {item}"
        config = {"item": "foo"}
        expected = "test foo"
        assert (
            snappy_device_agents._process_cmds_template_vars(cmds, config)
            == expected
        )

    def test_unknown_config_items(self):
        """Unknown config items should not cause an error"""
        cmds = "test  {unknown_item}"
        config = {}
        assert (
            snappy_device_agents._process_cmds_template_vars(cmds, config)
            == cmds
        )

    def test_escaped_braces(self):
        """Escaped braces should be unescaped, not interpreted"""
        cmds = "test {{item}}"
        config = {"item": "foo"}
        expected = "test {item}"
        assert (
            snappy_device_agents._process_cmds_template_vars(cmds, config)
            == expected
        )
