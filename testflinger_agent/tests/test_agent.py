import json
import os
import shutil
import tempfile
import uuid
import requests_mock as rmock
import pytest

from mock import patch

import testflinger_agent
from testflinger_agent.errors import TFServerError
from testflinger_agent.client import TestflingerClient as _TestflingerClient
from testflinger_agent.agent import TestflingerAgent as _TestflingerAgent


class TestClient:
    @pytest.fixture
    def agent(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config = {
            "agent_id": "test01",
            "polling_interval": "2",
            "server_address": "127.0.0.1:8000",
            "job_queues": ["test"],
            "execution_basedir": self.tmpdir,
            "logging_basedir": self.tmpdir,
            "results_basedir": os.path.join(self.tmpdir, "results"),
            "test_string": "ThisIsATest",
        }
        testflinger_agent.configure_logging(self.config)
        client = _TestflingerClient(self.config)
        yield _TestflingerAgent(client)
        # Inside tests, we patch rmtree so that we can check files after the
        # run, so we need to clean up the tmpdirs here
        shutil.rmtree(self.tmpdir)

    def test_check_and_run_setup(self, agent, requests_mock):
        self.config["setup_command"] = "echo setup1"
        fake_job_data = {"job_id": str(uuid.uuid1()), "job_queue": "test"}
        requests_mock.get(
            rmock.ANY, [{"text": json.dumps(fake_job_data)}, {"text": "{}"}]
        )
        requests_mock.post(rmock.ANY, status_code=200)
        with patch("shutil.rmtree"):
            agent.process_jobs()
        setuplog = open(
            os.path.join(self.tmpdir, fake_job_data.get("job_id"), "setup.log")
        ).read()
        assert "setup1" == setuplog.splitlines()[-1].strip()

    def test_check_and_run_provision(self, agent, requests_mock):
        self.config["provision_command"] = "echo provision1"
        fake_job_data = {
            "job_id": str(uuid.uuid1()),
            "job_queue": "test",
            "provision_data": {"url": "foo"},
        }
        requests_mock.get(
            rmock.ANY, [{"text": json.dumps(fake_job_data)}, {"text": "{}"}]
        )
        requests_mock.post(rmock.ANY, status_code=200)
        with patch("shutil.rmtree"):
            agent.process_jobs()
        provisionlog = open(
            os.path.join(
                self.tmpdir, fake_job_data.get("job_id"), "provision.log"
            )
        ).read()
        assert "provision1" == provisionlog.splitlines()[-1].strip()

    def test_check_and_run_test(self, agent, requests_mock):
        self.config["test_command"] = "echo test1"
        fake_job_data = {
            "job_id": str(uuid.uuid1()),
            "job_queue": "test",
            "test_data": {"test_cmds": "foo"},
        }
        requests_mock.get(
            rmock.ANY, [{"text": json.dumps(fake_job_data)}, {"text": "{}"}]
        )
        requests_mock.post(rmock.ANY, status_code=200)
        with patch("shutil.rmtree"):
            agent.process_jobs()
        testlog = open(
            os.path.join(self.tmpdir, fake_job_data.get("job_id"), "test.log")
        ).read()
        assert "test1" == testlog.splitlines()[-1].strip()

    def test_config_vars_in_env(self, agent, requests_mock):
        self.config["test_command"] = "echo test_string is $test_string"
        fake_job_data = {
            "job_id": str(uuid.uuid1()),
            "job_queue": "test",
            "test_data": {"test_cmds": "foo"},
        }
        requests_mock.get(
            rmock.ANY, [{"text": json.dumps(fake_job_data)}, {"text": "{}"}]
        )
        requests_mock.post(rmock.ANY, status_code=200)
        with patch("shutil.rmtree"):
            agent.process_jobs()
        testlog = open(
            os.path.join(self.tmpdir, fake_job_data.get("job_id"), "test.log")
        ).read()
        assert "ThisIsATest" in testlog

    def test_phase_failed(self, agent, requests_mock):
        # Make sure we stop running after a failed phase
        self.config["provision_command"] = "/bin/false"
        self.config["test_command"] = "echo test1"
        fake_job_data = {
            "job_id": str(uuid.uuid1()),
            "job_queue": "test",
            "provision_data": {"url": "foo"},
            "test_data": {"test_cmds": "foo"},
        }
        requests_mock.get(
            rmock.ANY, [{"text": json.dumps(fake_job_data)}, {"text": "{}"}]
        )
        requests_mock.post(rmock.ANY, status_code=200)
        with patch("shutil.rmtree"), patch("os.unlink"):
            agent.process_jobs()
        outcome_file = os.path.join(
            os.path.join(
                self.tmpdir,
                fake_job_data.get("job_id"),
                "testflinger-outcome.json",
            )
        )
        with open(outcome_file) as f:
            outcome_data = json.load(f)
        assert outcome_data.get("provision_status") == 1
        assert outcome_data.get("test_status") is None

    def test_retry_transmit(self, agent, requests_mock):
        # Make sure we retry sending test results
        self.config["provision_command"] = "/bin/false"
        self.config["test_command"] = "echo test1"
        fake_job_data = {"job_id": str(uuid.uuid1()), "job_queue": "test"}
        # Send an extra empty data since we will be calling get 3 times
        requests_mock.get(
            rmock.ANY,
            [
                {"text": json.dumps(fake_job_data)},
                {"text": "{}"},
                {"text": "{}"},
            ],
        )
        requests_mock.post(rmock.ANY, status_code=200)
        with patch.object(
            testflinger_agent.client.TestflingerClient, "transmit_job_outcome"
        ) as mock_transmit_job_outcome:
            # Make sure we fail the first time when transmitting the results
            mock_transmit_job_outcome.side_effect = [TFServerError(404), ""]
            agent.process_jobs()
            first_dir = os.path.join(
                self.config.get("execution_basedir"),
                fake_job_data.get("job_id"),
            )
            mock_transmit_job_outcome.assert_called_with(first_dir)
            # Try processing jobs again, now it should be in results_basedir
            agent.process_jobs()
            retry_dir = os.path.join(
                self.config.get("results_basedir"), fake_job_data.get("job_id")
            )
            mock_transmit_job_outcome.assert_called_with(retry_dir)

    def test_recovery_failed(self, agent, requests_mock):
        # Make sure we stop processing jobs after a device recovery error
        OFFLINE_FILE = "/tmp/TESTFLINGER-DEVICE-OFFLINE-test001"
        if os.path.exists(OFFLINE_FILE):
            os.unlink(OFFLINE_FILE)
        self.config["agent_id"] = "test001"
        self.config["provision_command"] = "exit 46"
        self.config["test_command"] = "echo test1"
        job_id = str(uuid.uuid1())
        fake_job_data = {
            "job_id": job_id,
            "job_queue": "test",
            "provision_data": {"url": "foo"},
            "test_data": {"test_cmds": "foo"},
        }
        # In this case we are making sure that the repost job request
        # gets good status
        with rmock.Mocker() as m:
            m.get(
                "http://127.0.0.1:8000/v1/job?queue=test", json=fake_job_data
            )
            m.get("http://127.0.0.1:8000/v1/result/" + job_id, text="{}")
            m.post("http://127.0.0.1:8000/v1/result/" + job_id, text="{}")
            m.post(
                "http://127.0.0.1:8000/v1/result/" + job_id + "/output",
                text="{}",
            )
            mpost_job_json = m.post(
                "http://127.0.0.1:8000/v1/job", json={"job_id": job_id}
            )
            agent.process_jobs()
            assert agent.check_offline()
            # These are the args we would expect when it reposts the job
            assert mpost_job_json.last_request.json() == fake_job_data
        if os.path.exists(OFFLINE_FILE):
            os.unlink(OFFLINE_FILE)
