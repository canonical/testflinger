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
from unittest import TestCase

import voluptuous

import testflinger_agent

GOOD_CONFIG = """
agent_id: test01
identifier: 12345-123456
polling_interval: 10
server_address: 127.0.0.1:8000
location: earth
job_queues:
    - test
"""

BAD_CONFIG = """
badkey: foo
"""


class ConfigTest(TestCase):
    def setUp(self):
        with tempfile.NamedTemporaryFile(delete=False) as config:
            self.configfile = config.name

    def tearDown(self):
        os.unlink(self.configfile)

    def test_config_good(self):
        with open(self.configfile, "w") as config:
            config.write(GOOD_CONFIG)
        config = testflinger_agent.load_config(self.configfile)
        self.assertEqual("test01", config.get("agent_id"))

    def test_config_bad(self):
        with open(self.configfile, "w") as config:
            config.write(BAD_CONFIG)
        self.assertRaises(
            voluptuous.error.MultipleInvalid,
            testflinger_agent.load_config,
            self.configfile,
        )
