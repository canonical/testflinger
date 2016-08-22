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
from testflinger_agent.errors import TFServerError

from mock import (patch, MagicMock)
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
                                    'results_basedir': os.path.join(
                                        self.tmpdir,
                                        'results')
                                    }
        testflinger_agent.configure_logging()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    @patch('shutil.rmtree')
    @patch('requests.post')
    @patch('requests.get')
    def test_check_and_run_setup(self, mock_requests_get, mock_requests_post,
                                 mock_rmtree):
        testflinger_agent.config['setup_command'] = 'echo setup1'
        fake_job_data = {'job_id': str(uuid.uuid1()),
                         'job_queue': 'test'}
        fake_response = requests.Response()
        fake_response._content = json.dumps(fake_job_data).encode()
        terminator = requests.Response()
        terminator._content = {}
        mock_requests_get.side_effect = [fake_response, terminator]
        # Make sure we return good status when posting the outcome
        # shutil.rmtree is mocked so that we avoid removing the files
        # before finishing the test
        mock_requests_post.side_effect = [MagicMock(status_code=200)]
        testflinger_agent.client.process_jobs()
        setuplog = open(os.path.join(self.tmpdir,
                                     fake_job_data.get('job_id'),
                                     'setup.log')).read()
        self.assertEqual('setup1', setuplog.strip())

    @patch('shutil.rmtree')
    @patch('requests.post')
    @patch('requests.get')
    def test_check_and_run_provision(self, mock_requests_get,
                                     mock_requests_post, mock_rmtree):
        testflinger_agent.config['provision_command'] = 'echo provision1'
        fake_job_data = {'job_id': str(uuid.uuid1()),
                         'job_queue': 'test'}
        fake_response = requests.Response()
        fake_response._content = json.dumps(fake_job_data).encode()
        terminator = requests.Response()
        terminator._content = {}
        mock_requests_get.side_effect = [fake_response, terminator]
        # Make sure we return good status when posting the outcome
        # shutil.rmtree is mocked so that we avoid removing the files
        # before finishing the test
        mock_requests_post.side_effect = [MagicMock(status_code=200)]
        testflinger_agent.client.process_jobs()
        provisionlog = open(os.path.join(self.tmpdir,
                                         fake_job_data.get('job_id'),
                                         'provision.log')).read()
        self.assertEqual('provision1', provisionlog.strip())

    @patch('shutil.rmtree')
    @patch('requests.post')
    @patch('requests.get')
    def test_check_and_run_test(self, mock_requests_get, mock_requests_post,
                                mock_rmtree):
        testflinger_agent.config['test_command'] = 'echo test1'
        fake_job_data = {'job_id': str(uuid.uuid1()),
                         'job_queue': 'test'}
        fake_response = requests.Response()
        fake_response._content = json.dumps(fake_job_data).encode()
        terminator = requests.Response()
        terminator._content = {}
        mock_requests_get.side_effect = [fake_response, terminator]
        # Make sure we return good status when posting the outcome
        # shutil.rmtree is mocked so that we avoid removing the files
        # before finishing the test
        mock_requests_post.side_effect = [MagicMock(status_code=200)]
        testflinger_agent.client.process_jobs()
        testlog = open(os.path.join(self.tmpdir,
                                    fake_job_data.get('job_id'),
                                    'test.log')).read()
        self.assertEqual('test1', testlog.strip())

    @patch('shutil.rmtree')
    @patch('requests.post')
    @patch('requests.get')
    def test_phase_failed(self, mock_requests_get, mock_requests_post,
                          mock_rmtree):
        """Make sure we stop running after a failed phase"""
        testflinger_agent.config['provision_command'] = '/bin/false'
        testflinger_agent.config['test_command'] = 'echo test1'
        fake_job_data = {'job_id': str(uuid.uuid1()),
                         'job_queue': 'test'}
        fake_response = requests.Response()
        fake_response._content = json.dumps(fake_job_data).encode()
        terminator = requests.Response()
        terminator._content = {}
        mock_requests_get.side_effect = [fake_response, terminator]
        # Make sure we return good status when posting the outcome
        # shutil.rmtree is mocked so that we avoid removing the files
        # before finishing the test
        mock_requests_post.side_effect = [MagicMock(status_code=200)]
        testflinger_agent.client.process_jobs()
        outcome_file = os.path.join(os.path.join(self.tmpdir,
                                                 fake_job_data.get('job_id'),
                                                 'testflinger-outcome.json'))
        with open(outcome_file) as f:
            outcome_data = json.load(f)
        self.assertEqual(1, outcome_data.get('provision_status'))
        self.assertEqual(None, outcome_data.get('test_status'))

    @patch('testflinger_agent.client.transmit_job_outcome')
    @patch('requests.get')
    def test_retry_transmit(self, mock_requests_get,
                            mock_transmit_job_outcome):
        """Make sure we retry sending test results"""
        testflinger_agent.config['provision_command'] = '/bin/false'
        testflinger_agent.config['test_command'] = 'echo test1'
        fake_job_data = {'job_id': str(uuid.uuid1()),
                         'job_queue': 'test'}
        fake_response = requests.Response()
        fake_response._content = json.dumps(fake_job_data).encode()
        terminator = requests.Response()
        terminator._content = {}
        # Send an extra terminator since we will be calling get 3 times
        mock_requests_get.side_effect = [fake_response, terminator, terminator]
        # Make sure we fail the first time when transmitting the results
        mock_transmit_job_outcome.side_effect = [TFServerError(404), 200]
        testflinger_agent.client.process_jobs()
        first_dir = os.path.join(
            testflinger_agent.config.get('execution_basedir'),
            fake_job_data.get('job_id'))
        mock_transmit_job_outcome.assert_called_with(first_dir)
        # Try processing the jobs again, now it should be in results_basedir
        testflinger_agent.client.process_jobs()
        retry_dir = os.path.join(
            testflinger_agent.config.get('results_basedir'),
            fake_job_data.get('job_id'))
        mock_transmit_job_outcome.assert_called_with(retry_dir)
