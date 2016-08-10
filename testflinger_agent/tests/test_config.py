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

import os
import tempfile
import testflinger_agent

from unittest import TestCase


class ConfigTest(TestCase):
    def setUp(self):
        with tempfile.NamedTemporaryFile(delete=False) as config:
            self.configfile = config.name
            config.write('agent_id: agent-foo'.encode())

    def tearDown(self):
        os.unlink(self.configfile)

    def test_config(self):
        testflinger_agent.load_config(self.configfile)
        self.assertEqual('agent-foo', testflinger_agent.config.get('agent_id'))
