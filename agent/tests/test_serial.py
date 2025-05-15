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
from testflinger_agent.job import (
    TestflingerJob as _TestflingerJob,
)
from testflinger_agent.runner import CommandRunner as _CommandRunner
from testflinger_agent.schema import validate


class TestSerialConsole:
    @pytest.fixture
    def client(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config = validate(
            {
                "agent_id": "test01",
                "polling_interval": 2,
                "server_address": "127.0.0.1:8000",
                "job_queues": ["test"],
                "execution_basedir": self.tmpdir,
                "logging_basedir": self.tmpdir,
                "results_basedir": os.path.join(self.tmpdir, "results"),
                "test_command": "/bin/true",
                "conserver_address": "console.example.com",
            }
        )
        testflinger_agent.configure_logging(self.config)
        yield _TestflingerClient(self.config)
        shutil.rmtree(self.tmpdir)

    def test_job_with_serial_capture(self, client, requests_mock):
        """Test that serial logs are captured while a job is running"""
        job_id = "test-job-123"
        fake_job_data = {
            "job_id": job_id,
            "job_queue": "test",
            "test_data": {"test_cmds": "echo test1"},
        }
        job = _TestflingerJob(fake_job_data, client)

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
                rundir = os.path.join(self.tmpdir, job_id)
                job.run_test_phase("test", rundir)
                print("done running")
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
                assert "log_data" in serial_posts[0].json
                assert serial_posts[0].json["log_data"] == "serial_log"
