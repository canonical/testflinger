import json
import os
import requests
import shutil
import tempfile
import uuid

from mock import (patch, MagicMock)
from unittest import TestCase

import testflinger_agent
from testflinger_agent.errors import TFServerError
from testflinger_agent.client import TestflingerClient
from testflinger_agent.agent import TestflingerAgent


class ClientRunTests(TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config = {'agent_id': 'test01',
                       'polling_interval': '2',
                       'server_address': '127.0.0.1:8000',
                       'job_queues': ['test'],
                       'execution_basedir': self.tmpdir,
                       'logging_basedir': self.tmpdir,
                       'results_basedir': os.path.join(self.tmpdir, 'results')
                       }
        testflinger_agent.configure_logging(self.config)

    def get_agent(self):
        client = TestflingerClient(self.config)
        return TestflingerAgent(client)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    @patch('shutil.rmtree')
    @patch('requests.post')
    @patch('requests.get')
    def test_check_and_run_setup(self, mock_requests_get, mock_requests_post,
                                 mock_rmtree):
        self.config['setup_command'] = 'echo setup1'
        agent = self.get_agent()
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
        mock_requests_post.return_value = MagicMock(status_code=200)
        agent.process_jobs()
        setuplog = open(os.path.join(self.tmpdir,
                                     fake_job_data.get('job_id'),
                                     'setup.log')).read()
        self.assertEqual('setup1', setuplog.splitlines()[-1].strip())

    @patch('shutil.rmtree')
    @patch('requests.post')
    @patch('requests.get')
    def test_check_and_run_provision(self, mock_requests_get,
                                     mock_requests_post, mock_rmtree):
        self.config['provision_command'] = 'echo provision1'
        agent = self.get_agent()
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
        mock_requests_post.return_value = MagicMock(status_code=200)
        agent.process_jobs()
        provisionlog = open(os.path.join(self.tmpdir,
                                         fake_job_data.get('job_id'),
                                         'provision.log')).read()
        self.assertEqual('provision1', provisionlog.splitlines()[-1].strip())

    @patch('shutil.rmtree')
    @patch('requests.post')
    @patch('requests.get')
    def test_check_and_run_test(self, mock_requests_get, mock_requests_post,
                                mock_rmtree):
        self.config['test_command'] = 'echo test1'
        agent = self.get_agent()
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
        mock_requests_post.return_value = MagicMock(status_code=200)
        agent.process_jobs()
        testlog = open(os.path.join(self.tmpdir,
                                    fake_job_data.get('job_id'),
                                    'test.log')).read()
        self.assertEqual('test1', testlog.splitlines()[-1].strip())

    @patch('testflinger_agent.client.os.unlink')
    @patch('shutil.rmtree')
    @patch('requests.post')
    @patch('requests.get')
    def test_phase_failed(self, mock_requests_get, mock_requests_post,
                          mock_rmtree, mock_unlink):
        """Make sure we stop running after a failed phase"""
        self.config['provision_command'] = '/bin/false'
        self.config['test_command'] = 'echo test1'
        agent = self.get_agent()
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
        mock_requests_post.return_value = MagicMock(status_code=200)
        agent.process_jobs()
        outcome_file = os.path.join(os.path.join(self.tmpdir,
                                                 fake_job_data.get('job_id'),
                                                 'testflinger-outcome.json'))
        with open(outcome_file) as f:
            outcome_data = json.load(f)
        self.assertEqual(1, outcome_data.get('provision_status'))
        self.assertEqual(None, outcome_data.get('test_status'))

    @patch('testflinger_agent.client.logger.exception')
    @patch.object(testflinger_agent.client.TestflingerClient,
                  'transmit_job_outcome')
    @patch('requests.get')
    @patch('requests.post')
    def test_retry_transmit(self, mock_requests_post, mock_requests_get,
                            mock_transmit_job_outcome,
                            mock_logger_exception):
        """Make sure we retry sending test results"""
        self.config['provision_command'] = '/bin/false'
        self.config['test_command'] = 'echo test1'
        agent = self.get_agent()
        fake_job_data = {'job_id': str(uuid.uuid1()),
                         'job_queue': 'test'}
        fake_response = requests.Response()
        fake_response._content = json.dumps(fake_job_data).encode()
        terminator = requests.Response()
        terminator._content = {}
        # Send an extra terminator since we will be calling get 3 times
        mock_requests_get.side_effect = [fake_response, terminator, terminator]
        # Make sure we fail the first time when transmitting the results
        mock_transmit_job_outcome.side_effect = [TFServerError(404),
                                                 terminator, terminator]
        mock_requests_post.return_value = MagicMock(status_code=200)
        agent.process_jobs()
        first_dir = os.path.join(
            self.config.get('execution_basedir'),
            fake_job_data.get('job_id'))
        mock_transmit_job_outcome.assert_called_with(first_dir)
        # Try processing the jobs again, now it should be in results_basedir
        agent.process_jobs()
        retry_dir = os.path.join(
            self.config.get('results_basedir'),
            fake_job_data.get('job_id'))
        mock_transmit_job_outcome.assert_called_with(retry_dir)

    @patch('testflinger_agent.client.logger.exception')
    @patch('requests.post')
    @patch('requests.get')
    def test_post_artifact(self, mock_requests_get,
                           mock_requests_post,
                           mock_logger_exception):
        """Test posting files from the artifact directory"""
        # Create an artifact as part of the test process
        self.config['test_command'] = ('mkdir artifacts && '
                                       'echo test1 > artifacts/t')
        agent = self.get_agent()
        fake_job_data = {'job_id': str(uuid.uuid1()),
                         'job_queue': 'test'}
        fake_response = requests.Response()
        fake_response._content = json.dumps(fake_job_data).encode()
        terminator = requests.Response()
        terminator._content = {}
        # Send an extra terminator since we will be calling get 3 times
        mock_requests_get.side_effect = [fake_response, terminator, terminator]
        # Make sure we fail the first time when transmitting the results
        mock_requests_post.return_value = MagicMock(status_code=200)
        agent.process_jobs()
        # The last request should have the 'files' value we are looking for
        self.assertTrue('files' in str(mock_requests_post.mock_calls[-1]))

    @patch('shutil.rmtree')
    @patch('requests.post')
    @patch('requests.get')
    def test_recovery_failed(self, mock_requests_get, mock_requests_post,
                             mock_rmtree):
        """Make sure we stop processing jobs after a device recovery error"""
        OFFLINE_FILE = '/tmp/TESTFLINGER-DEVICE-OFFLINE-test001'
        if os.path.exists(OFFLINE_FILE):
            os.unlink(OFFLINE_FILE)
        self.config['agent_id'] = 'test001'
        self.config['provision_command'] = 'exit 46'
        self.config['test_command'] = 'echo test1'
        agent = self.get_agent()
        fake_job_data = {'job_id': str(uuid.uuid1()),
                         'job_queue': 'test'}
        fake_response = requests.Response()
        fake_response._content = json.dumps(fake_job_data).encode()
        terminator = requests.Response()
        terminator._content = {}
        mock_requests_get.side_effect = [fake_response, terminator]
        # In this case we are making sure that the repost job request
        # gets good status
        mock_requests_post.return_value = MagicMock(status_code=200)
        agent.process_jobs()
        self.assertEqual(True, agent.check_offline())
        # These are the args we would expect when it reposts the job
        repost_args = ('http://127.0.0.1:8000/v1/job')
        repost_kwargs = dict(json=fake_job_data)
        mock_requests_post.assert_called_with(repost_args, **repost_kwargs)
        if os.path.exists(OFFLINE_FILE):
            os.unlink(OFFLINE_FILE)
