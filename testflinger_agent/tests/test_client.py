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
import tempfile
import os
import shutil
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


class ClientRunTests(TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        testflinger_agent.config = {'agent_id': 'test01',
                                    'polling_interval': '2',
                                    'server_address': '127.0.0.1:8000',
                                    'job_queues': ['test'],
                                    'execution_basedir': self.tmpdir,
                                    'logging_basedir': self.tmpdir,
                                    }

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    @patch('requests.post')
    @patch('requests.get')
    def test_check_and_run_setup(self, mock_requests_get, mock_requests_post):
        testflinger_agent.config['setup_command'] = 'echo setup1'
        fake_job_data = {'job_id': str(uuid.uuid1()),
                         'job_queue': 'test'}
        fake_response = requests.Response()
        fake_response._content = json.dumps(fake_job_data).encode()
        mock_requests_get.return_value = fake_response
        testflinger_agent.client.process_jobs()
        setuplog = open(os.path.join(self.tmpdir,
                                     fake_job_data.get('job_id'),
                                     'setup.log')).read()
        self.assertEqual('setup1', setuplog.strip())

    @patch('requests.post')
    @patch('requests.get')
    def test_check_and_run_provision(self, mock_requests_get,
                                     mock_requests_post):
        testflinger_agent.config['provision_command'] = 'echo provision1'
        fake_job_data = {'job_id': str(uuid.uuid1()),
                         'job_queue': 'test'}
        fake_response = requests.Response()
        fake_response._content = json.dumps(fake_job_data).encode()
        mock_requests_get.return_value = fake_response
        testflinger_agent.client.process_jobs()
        provisionlog = open(os.path.join(self.tmpdir,
                                         fake_job_data.get('job_id'),
                                         'provision.log')).read()
        self.assertEqual('provision1', provisionlog.strip())

    @patch('requests.post')
    @patch('requests.get')
    def test_check_and_run_test(self, mock_requests_get, mock_requests_post):
        testflinger_agent.config['test_command'] = 'echo test1'
        fake_job_data = {'job_id': str(uuid.uuid1()),
                         'job_queue': 'test'}
        fake_response = requests.Response()
        fake_response._content = json.dumps(fake_job_data).encode()
        mock_requests_get.return_value = fake_response
        testflinger_agent.client.process_jobs()
        testlog = open(os.path.join(self.tmpdir,
                                    fake_job_data.get('job_id'),
                                    'test.log')).read()
        self.assertEqual('test1', testlog.strip())
