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
import requests
import uuid

import testflinger_agent

from mock import patch
from unittest import TestCase


class ClientTest(TestCase):
    @patch('requests.get')
    def test_check_jobs_empty(self, mock_requests_get):
        mock_requests_get.return_value = requests.Response()
        job_data = testflinger_agent.client.check_jobs()
        self.assertEqual(job_data, None)

    @patch('requests.get')
    def test_check_jobs_with_job(self, mock_requests_get):
        fake_job_data = {'job_id': str(uuid.uuid1()),
                         'job_queue': 'test_queue'}
        fake_response = requests.Response()
        fake_response._content = json.dumps(fake_job_data).encode()
        mock_requests_get.return_value = fake_response
        job_data = testflinger_agent.client.check_jobs()
        self.assertEqual(job_data, fake_job_data)
