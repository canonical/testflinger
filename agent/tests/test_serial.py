import json
import os
import shutil
import tempfile
from unittest.mock import patch

import pytest
import requests_mock as rmock

import testflinger_agent
from testflinger_agent.agent import TestflingerAgent as _TestflingerAgent
from testflinger_agent.client import TestflingerClient as _TestflingerClient
from testflinger_agent.runner import CommandRunner as _CommandRunner
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
                "test_command": "echo test",
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

    def test_job_with_serial_capture(self, agent, requests_mock):
        """Test that serial logs are captured while a job is running."""
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

        def mock_command_runner(cwd, env):
            runner = _CommandRunner(cwd=cwd, env=env)
            original_run_serial = runner.run_command_thread
            runner.run_command_thread = lambda _cmd: original_run_serial(
                "echo serial_log"
            )
            return runner

        with patch(
            "testflinger_agent.job.CommandRunner",
            mock_command_runner,
        ):
            with patch("shutil.rmtree"):
                agent.process_jobs()
                rundir = os.path.join(self.tmpdir, job_id)

                with open(
                    os.path.join(rundir, "test-serial-conserver.log")
                ) as f:
                    serial_log = f.read()
                    assert "serial_log" in serial_log

                serial_posts = [
                    req
                    for req in requests_mock.request_history
                    if req.path == f"/v1/result/{job_id}/log/serial"
                ]
                assert len(serial_posts) == 1
                assert "serial_log" in serial_posts[0].text
