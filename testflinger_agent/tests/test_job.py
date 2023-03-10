import os
import pytest
import shutil
import tempfile

import requests_mock as rmock

import testflinger_agent
from testflinger_agent.client import TestflingerClient as _TestflingerClient
from testflinger_agent.job import TestflingerJob as _TestflingerJob


class TestJob:
    @pytest.fixture
    def client(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config = {
            "agent_id": "test01",
            "polling_interval": "2",
            "server_address": "127.0.0.1:8000",
            "job_queues": ["test"],
            "execution_basedir": self.tmpdir,
            "logging_basedir": self.tmpdir,
            "results_basedir": os.path.join(self.tmpdir, "results"),
        }
        testflinger_agent.configure_logging(self.config)
        yield _TestflingerClient(self.config)
        shutil.rmtree(self.tmpdir)

    def test_skip_missing_provision_data(self, client):
        """
        Test that provision phase is skipped when provision_data is
        absent
        """
        self.config["provision_command"] = "/bin/true"
        fake_job_data = {"global_timeout": 1}
        job = _TestflingerJob(fake_job_data, client)
        job.run_test_phase("provision", None)
        logfile = os.path.join(self.tmpdir, "testflinger-agent.log")
        with open(logfile) as log:
            log_output = log.read()
        assert "No provision_data defined in job data" in log_output

    def test_skip_empty_provision_data(self, client):
        """
        Test that provision phase is skipped when provision_data is
        present but empty
        """
        self.config["provision_command"] = "/bin/true"
        fake_job_data = {"global_timeout": 1, "provision_data": ""}
        job = _TestflingerJob(fake_job_data, client)
        job.run_test_phase("provision", None)
        logfile = os.path.join(self.tmpdir, "testflinger-agent.log")
        with open(logfile) as log:
            log_output = log.read()
        assert "No provision_data defined in job data" in log_output

    def test_job_global_timeout(self, client, requests_mock):
        """Test that timeout from job_data is respected"""
        timeout_str = "\nERROR: Global timeout reached! (1s)\n"
        logfile = os.path.join(self.tmpdir, "testlog")
        fake_job_data = {"global_timeout": 1}
        requests_mock.post(rmock.ANY, status_code=200)
        requests_mock.get(rmock.ANY, status_code=200)
        job = _TestflingerJob(fake_job_data, client)
        job.phase = "test"
        job.run_with_log("sleep 3", logfile)
        with open(logfile) as log:
            log_data = log.read()
        assert timeout_str == log_data

    def test_config_global_timeout(self, client, requests_mock):
        """Test that timeout from device config is preferred"""
        timeout_str = "\nERROR: Global timeout reached! (1s)\n"
        logfile = os.path.join(self.tmpdir, "testlog")
        self.config["global_timeout"] = 1
        fake_job_data = {"global_timeout": 3}
        requests_mock.post(rmock.ANY, status_code=200)
        requests_mock.get(rmock.ANY, status_code=200)
        job = _TestflingerJob(fake_job_data, client)
        job.phase = "test"
        job.run_with_log("sleep 3", logfile)
        with open(logfile) as log:
            log_data = log.read()
        assert timeout_str == log_data

    def test_job_output_timeout(self, client, requests_mock):
        """Test that output timeout from job_data is respected"""
        timeout_str = "\nERROR: Output timeout reached! (1s)\n"
        logfile = os.path.join(self.tmpdir, "testlog")
        fake_job_data = {"output_timeout": 1}
        requests_mock.post(rmock.ANY, status_code=200)
        requests_mock.get(rmock.ANY, status_code=200)
        job = _TestflingerJob(fake_job_data, client)
        job.phase = "test"
        # unfortunately, we need to sleep for longer that 10 seconds here
        # or else we fall under the polling time
        job.run_with_log("sleep 12", logfile)
        with open(logfile) as log:
            log_data = log.read()
        assert timeout_str == log_data

    def test_config_output_timeout(self, client, requests_mock):
        """Test that output timeout from device config is preferred"""
        timeout_str = "\nERROR: Output timeout reached! (1s)\n"
        logfile = os.path.join(self.tmpdir, "testlog")
        self.config["output_timeout"] = 1
        fake_job_data = {"output_timeout": 30}
        requests_mock.post(rmock.ANY, status_code=200)
        requests_mock.get(rmock.ANY, status_code=200)
        job = _TestflingerJob(fake_job_data, client)
        job.phase = "test"
        # unfortunately, we need to sleep for longer that 10 seconds here
        # or else we fall under the polling time
        job.run_with_log("sleep 12", logfile)
        with open(logfile) as log:
            log_data = log.read()
        assert timeout_str == log_data

    def test_no_output_timeout_in_provision(self, client, requests_mock):
        """Test that output timeout is ignored when not in test phase"""
        timeout_str = "complete\n"
        logfile = os.path.join(self.tmpdir, "testlog")
        fake_job_data = {"output_timeout": 1}
        requests_mock.post(rmock.ANY, status_code=200)
        requests_mock.get(rmock.ANY, status_code=200)
        job = _TestflingerJob(fake_job_data, client)
        job.phase = "provision"
        # unfortunately, we need to sleep for longer that 10 seconds here
        # or else we fall under the polling time
        job.run_with_log("sleep 12 && echo complete", logfile)
        with open(logfile) as log:
            log_data = log.read()
        assert timeout_str == log_data

    def test_set_truncate(self, client):
        """Test the _set_truncate method of TestflingerJob"""
        job = _TestflingerJob({}, client)
        with tempfile.TemporaryFile(mode="r+") as f:
            # First check that a small file doesn't get truncated
            f.write("x" * 100)
            job._set_truncate(f, size=100)
            contents = f.read()
            assert len(contents) == 100
            assert "WARNING" not in contents

            # Now check that a larger file does get truncated
            f.write("x" * 100)
            job._set_truncate(f, size=100)
            contents = f.read()
            # It won't be exactly 100 bytes, because a warning is added
            assert len(contents) < 150
            assert "WARNING" in contents
