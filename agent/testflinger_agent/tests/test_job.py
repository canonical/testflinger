import json
import os
import pytest
import re
import shutil
import tempfile

import requests_mock as rmock
from unittest.mock import patch

import testflinger_agent
from testflinger_agent.client import TestflingerClient as _TestflingerClient
from testflinger_agent.job import TestflingerJob as _TestflingerJob
from testflinger_agent.runner import CommandRunner
from testflinger_agent.handlers import LogUpdateHandler
from testflinger_agent.stop_condition_checkers import (
    GlobalTimeoutChecker,
    OutputTimeoutChecker,
)
from testflinger_common.enums import TestEvent, TestPhase


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

    @pytest.mark.parametrize(
        "phase",
        ["provision", "firmware_update", "test", "allocate", "reserve"],
    )
    def test_skip_missing_data(self, client, phase):
        """
        Test that optional phases are skipped when the data is missing
        """
        fake_job_data = {"global_timeout": 1, "provision_data": ""}
        job = _TestflingerJob(fake_job_data, client)

        self.config[f"{phase}_command"] = "/bin/true"
        return_value, exit_event, exit_reason = job.run_test_phase(phase, None)
        assert return_value == 0
        assert exit_event is None
        assert exit_reason is None

    @pytest.mark.parametrize(
        "phase", ["setup", "provision", "test", "allocate", "reserve"]
    )
    def test_skip_empty_provision_data(self, client, phase):
        """
        Test that phases are skipped when there is no command configured
        """
        self.config[f"{phase}_command"] = ""
        fake_job_data = {"global_timeout": 1, f"{phase}_data": "foo"}
        job = _TestflingerJob(fake_job_data, client)
        return_value, exit_event, exit_reason = job.run_test_phase(phase, None)
        assert return_value == 0
        assert exit_event is None
        assert exit_reason is None

    def test_job_global_timeout(self, tmp_path):
        """Test that timeout from job_data is respected"""
        timeout_str = "ERROR: Global timeout reached! (1s)"
        logfile = tmp_path / "testlog"
        runner = CommandRunner(tmp_path, env={})
        log_handler = LogUpdateHandler(logfile)
        runner.register_output_handler(log_handler)
        global_timeout_checker = GlobalTimeoutChecker(1)
        runner.register_stop_condition_checker(global_timeout_checker)
        exit_code, exit_event, exit_reason = runner.run("sleep 12")
        with open(logfile) as log:
            log_data = log.read()
        assert timeout_str in log_data
        assert exit_reason == timeout_str
        assert exit_code == -9
        assert exit_event == TestEvent.GLOBAL_TIMEOUT

    def test_config_global_timeout(self, client):
        """Test that timeout from device config is preferred"""
        self.config["global_timeout"] = 1
        fake_job_data = {"global_timeout": 3}
        job = _TestflingerJob(fake_job_data, client)
        timeout = job.get_global_timeout()
        assert timeout == 1

    def test_job_output_timeout(self, tmp_path):
        """Test that output timeout from job_data is respected"""
        timeout_str = "ERROR: Output timeout reached! (1s)"
        logfile = tmp_path / "testlog"
        runner = CommandRunner(tmp_path, env={})
        log_handler = LogUpdateHandler(logfile)
        runner.register_output_handler(log_handler)
        output_timeout_checker = OutputTimeoutChecker(1)
        runner.register_stop_condition_checker(output_timeout_checker)
        # unfortunately, we need to sleep for longer that 10 seconds here
        # or else we fall under the polling time
        exit_code, exit_event, exit_reason = runner.run("sleep 12")
        with open(logfile) as log:
            log_data = log.read()
        assert timeout_str in log_data
        assert exit_reason == timeout_str
        assert exit_code == -9
        assert exit_event == TestEvent.OUTPUT_TIMEOUT

    def test_config_output_timeout(self, client):
        """Test that output timeout from device config is preferred"""
        self.config["output_timeout"] = 1
        fake_job_data = {"output_timeout": 3}
        job = _TestflingerJob(fake_job_data, client)
        timeout = job.get_output_timeout()
        assert timeout == 1

    def test_no_output_timeout_in_provision(
        self, client, tmp_path, requests_mock
    ):
        """Test that output timeout is ignored when not in test phase"""
        timeout_str = "complete\n"
        logfile = tmp_path / "provision.log"
        fake_job_data = {"output_timeout": 1, "provision_data": {"url": "foo"}}
        self.config["provision_command"] = (
            "bash -c 'sleep 12 && echo complete'"
        )
        requests_mock.post(rmock.ANY, status_code=200)
        job = _TestflingerJob(fake_job_data, client)
        job.phase = "provision"

        # create the outcome file since we bypassed that
        with open(tmp_path / "testflinger-outcome.json", "w") as outcome_file:
            outcome_file.write("{}")

        # unfortunately, we need to sleep for longer that 10 seconds here
        # or else we fall under the polling time
        # job.run_with_log("sleep 12 && echo complete", logfile)
        job.run_test_phase("provision", tmp_path)
        with open(logfile) as log:
            log_data = log.read()
        assert timeout_str in log_data

    def test_run_test_phase_with_run_exception(
        self, client, tmp_path, requests_mock
    ):
        """
        Test that job.run_test_phase() exits with 100 so that it has some
        non-zero value if CommandRunner.run() raises an exception
        """

        # create the outcome file since we bypassed that
        with open(tmp_path / "testflinger-outcome.json", "w") as outcome_file:
            outcome_file.write("{}")

        self.config["setup_command"] = "fake_setup_command"
        requests_mock.post(rmock.ANY, status_code=200)
        job = _TestflingerJob({}, client)
        job.phase = "setup"
        # Don't raise the exception on the 3 banner lines
        with patch(
            "testflinger_agent.job.CommandRunner.run",
            side_effect=[None, None, None, Exception("failed")],
        ):
            exit_code, exit_event, exit_reason = job.run_test_phase(
                "setup", tmp_path
            )
        assert exit_code == 100
        assert exit_event == "setup_fail"
        assert exit_reason == "failed"

    def run_testcmds(self, job_data, client, tmp_path) -> str:
        # create the outcome file manually
        with open(tmp_path / "testflinger-outcome.json", "w") as outcome_file:
            outcome_file.write("{}")
        # create the agent configuration file manually
        with open(tmp_path / "default.yaml", "w") as config_file:
            config_file.write("agent_name: agent-007")
        # write the job data to `testflinger.json` manually:
        # (so that the device connector can pick it up)
        with open(tmp_path / "testflinger.json", "w") as job_file:
            json.dump(job_data, job_file)

        # running the device connector will result in running the `test_cmds`
        self.config["test_command"] = (
            "testflinger-device-connector fake_connector runtest "
            f"--config {tmp_path}/default.yaml "
            f"{tmp_path}/testflinger.json"
        )

        # run the test phase of the job
        job = _TestflingerJob(job_data, client)
        exit_code, _, _ = job.run_test_phase(TestPhase.TEST, tmp_path)
        assert exit_code == 0

        # capture the output
        with open(tmp_path / "test.log") as log:
            return log.read()

    def test_run_test_phase_sensitive(self, client, tmp_path, requests_mock):
        requests_mock.post(rmock.ANY, status_code=200)

        # sensitive patterns are added to the agent configuration file:
        # this will result in the use of a masking command runner
        self.config["sensitive_patterns"] = ["[Cc][a-z]*n"]

        # create the job data
        job_data = {
            "test_data": {"test_cmds": "echo -n Message: Captain Major"}
        }

        log_data = self.run_testcmds(job_data, client, tmp_path)
        print(log_data)

        # the output should match this pattern, i.e. the sensitive pattern
        # after "Message: " should be masked
        output_pattern = r"^Message: \*\*([0-9a-f]{6})\*\* Major$"
        match = re.search(output_pattern, log_data, re.MULTILINE)
        assert match is not None

    def test_run_test_phase_secret(self, client, tmp_path, requests_mock):
        requests_mock.post(rmock.ANY, status_code=200)

        # create the job data
        job_data = {
            "secrets": {"SECRET": "Major"},
            "test_data": {
                "test_cmds": "echo -n Message: Captain Major $SECRET"
            },
        }

        log_data = self.run_testcmds(job_data, client, tmp_path)
        print(log_data)

        # the output should match this pattern, i.e. the secrets
        # after "Message: " should be masked
        output_pattern = (
            r"^Message: Captain \*\*([0-9a-f]{6})\*\* \*\*([0-9a-f]{6})\*\*$"
        )
        match = re.search(output_pattern, log_data, re.MULTILINE)
        assert match is not None
        first, second = match.groups()
        assert first == second

    def test_run_test_phase_sensitive_and_secret(
        self, client, tmp_path, requests_mock
    ):
        requests_mock.post(rmock.ANY, status_code=200)

        # sensitive patterns are added to the agent configuration file:
        self.config["sensitive_patterns"] = ["[Cc][a-z]*n"]

        # create the job data
        job_data = {
            "secrets": {"SECRET": "Major"},
            "test_data": {
                "test_cmds": "echo -n Message: Captain Major $SECRET"
            },
        }

        log_data = self.run_testcmds(job_data, client, tmp_path)
        print(log_data)

        # the output should match this pattern, i.e. the strings
        # after "Message: " should be masked
        output_pattern = (
            r"^Message: "
            r"\*\*([0-9a-f]{6})\*\* "
            r"\*\*([0-9a-f]{6})\*\* "
            r"\*\*([0-9a-f]{6})\*\*$"
        )
        match = re.search(output_pattern, log_data, re.MULTILINE)
        assert match is not None
        first, second, third = match.groups()
        assert first != second and second == third

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

    @pytest.mark.timeout(1)
    def test_wait_for_completion(self, client):
        """Test that wait_for_completion works"""

        # Make sure we return "completed" for the parent job state
        client.check_job_state = lambda _: "completed"

        job = _TestflingerJob({"parent_job_id": "999"}, client)
        job.wait_for_completion()
        # No assertions needed, just make sure we don't timeout
