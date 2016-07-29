# Copyright (C) 2016 Canonical
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

import json
import testflinger

from unittest import TestCase


class APITest(TestCase):

    def setUp(self):
        self.app = testflinger.app.test_client()

    def test_home(self):
        output = self.app.get('/')
        self.assertEqual('Testflinger Server', output.data.decode())

    def test_add_job(self):
        output = self.app.post('/v1/job')
        job_id = json.loads(output.data.decode()).get('job_id')
        self.assertTrue(testflinger.v1.check_valid_uuid(job_id))

    def test_result_get_good(self):
        output = self.app.get(
            '/v1/result/00000000-0000-0000-0000-000000000000')
        self.assertEqual('OK', output.data.decode())

    def test_result_get_bad(self):
        output = self.app.get('/v1/result/BAD_JOB_ID')
        self.assertEqual('Invalid job id\n', output.data.decode())
        self.assertEqual(400, output.status_code)

    def test_result_post_good(self):
        output = self.app.post(
            '/v1/result/00000000-0000-0000-0000-000000000000')
        self.assertEqual('OK', output.data.decode())

    def test_result_post_bad(self):
        output = self.app.post('/v1/result/BAD_JOB_ID')
        self.assertEqual('Invalid job id\n', output.data.decode())
        self.assertEqual(400, output.status_code)
