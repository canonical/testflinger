import os
import shutil
import tempfile

from mock import patch
from unittest import TestCase

import testflinger_agent
from testflinger_agent.client import TestflingerClient
from testflinger_agent.job import TestflingerJob


class JobTests(TestCase):
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

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_job_global_timeout(self):
        """Test that timeout from job_data is respected"""
        timeout_str = '\nERROR: Global timeout reached! (1s)\n'
        logfile = os.path.join(self.tmpdir, 'testlog')
        client = TestflingerClient(self.config)
        fake_job_data = {'global_timeout': 1}
        patch('client.post_live_output')
        job = TestflingerJob(fake_job_data, client)
        job.run_with_log('sleep 3', logfile)
        with open(logfile) as log:
            log_data = log.read()
        self.assertEqual(timeout_str, log_data)

    def test_config_global_timeout(self):
        """Test that timeout from device config is preferred"""
        timeout_str = '\nERROR: Global timeout reached! (1s)\n'
        logfile = os.path.join(self.tmpdir, 'testlog')
        self.config['global_timeout'] = 1
        client = TestflingerClient(self.config)
        fake_job_data = {'global_timeout': 3}
        patch('client.post_live_output')
        job = TestflingerJob(fake_job_data, client)
        job.run_with_log('sleep 3', logfile)
        with open(logfile) as log:
            log_data = log.read()
        self.assertEqual(timeout_str, log_data)
