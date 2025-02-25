import json
import os
import tempfile
import shutil
from unittest.mock import patch

import pytest
import requests_mock as rmock

import testflinger_agent
from testflinger_agent.client import TestflingerClient as _TestflingerClient
from testflinger_agent.agent import TestflingerAgent as _TestflingerAgent
from testflinger_agent.schema import validate


class TestSerialConsole:
    @pytest.fixture
    def agent(self, requests_mock):
        self.tmpdir = tempfile.mkdtemp()
        self.config = validate(
            {
                "agent_id": "test01",
                "identifier": "12345-123456",
                "polling_interval": 2,
                "server_address": "127.0.0.1:8000",
                "job_queues": ["test"],
                "location": "nowhere",
                "provision_type": "noprovision",
                "execution_basedir": self.tmpdir,
                "logging_basedir": self.tmpdir,
                "results_basedir": os.path.join(self.tmpdir, "results"),
                "conserver_address": "console.example.com",
            }
        )
        testflinger_agent.configure_logging(self.config)
        client = _TestflingerClient(self.config)
        requests_mock.get(rmock.ANY)
        requests_mock.post(rmock.ANY)
        yield _TestflingerAgent(client)
        # Clean up tmpdir after tests
        shutil.rmtree(self.tmpdir)

    def test_start_serial_capture(self, agent):
        """
        Tests that the console command is called when starting serial
        log capture.
        """
        with patch.object(agent, "conserver_runner") as mock_runner:
            job_id = "test-job-123"
            rundir = os.path.join(self.tmpdir, job_id)
            os.makedirs(rundir)
            agent.start_serial_log_capture(rundir, job_id)
            assert mock_runner.register_output_handler.call_count == 2
            expected_cmd = (
                f"console -M {self.config['conserver_address']} "
                f"{self.config['agent_id']}"
            )
            mock_runner.run_async.assert_called_once_with(expected_cmd)

    def test_job_with_serial_capture(self, agent, requests_mock):
        """Test that serial logs are captured while a job is running"""
        job_id = "test-job-123"
        fake_job_data = {
            "job_id": job_id,
            "job_queue": "test",
            "test_data": {"test_cmds": "echo test1"},
        }

        requests_mock.get(
            rmock.ANY, [{"text": json.dumps(fake_job_data)}, {"text": "{}"}]
        )
        requests_mock.post(rmock.ANY, status_code=200)

        original_run_serial = agent.conserver_runner.run_command_thread

        def mock_run_serial(cmd):
            original_run_serial("echo serial_log")

        with patch("shutil.rmtree"):
            agent.conserver_runner.run_command_thread = mock_run_serial
            agent.process_jobs()
            rundir = os.path.join(self.tmpdir, job_id)

            with open(os.path.join(rundir, "full-serial.log")) as f:
                serial_log = f.read()
                assert "serial_log" in serial_log

            serial_posts = [
                req
                for req in requests_mock.request_history
                if req.path == f"/v1/result/{job_id}/serial_output"
            ]
            assert len(serial_posts) == 1
            assert "serial_log" in serial_posts[0].text
