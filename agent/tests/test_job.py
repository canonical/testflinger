import json
import os
import re
import shutil
import tempfile
import uuid
from http import HTTPStatus
from unittest.mock import patch

import pytest
import requests_mock as rmock
from testflinger_common.enums import TestEvent, TestPhase

import testflinger_agent
from testflinger_agent.client import TestflingerClient as _TestflingerClient
from testflinger_agent.handlers import FileLogHandler
from testflinger_agent.job import (
    TestflingerJob as _TestflingerJob,
)
from testflinger_agent.runner import CommandRunner
from testflinger_agent.schema import validate
from testflinger_agent.stop_condition_checkers import (
    GlobalTimeoutChecker,
    OutputTimeoutChecker,
)


class TestJob:
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
            }
        )
        testflinger_agent.configure_logging(self.config)
        yield _TestflingerClient(self.config)
        shutil.rmtree(self.tmpdir)

    @pytest.mark.parametrize(
        "phase",
        ["provision", "firmware_update", "test", "allocate", "reserve"],
    )
    def test_skip_missing_data(self, client, phase):
        """Test that optional phases are skipped when the data is missing."""
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
        """Test that phases are skipped when there is no command configured."""
        self.config[f"{phase}_command"] = ""
        fake_job_data = {"global_timeout": 1, f"{phase}_data": "foo"}
        job = _TestflingerJob(fake_job_data, client)
        return_value, exit_event, exit_reason = job.run_test_phase(phase, None)
        assert return_value == 0
        assert exit_event is None
        assert exit_reason is None

    def test_job_global_timeout(self, tmp_path):
        """Test that timeout from job_data is respected."""
        timeout_str = "ERROR: Global timeout reached! (1s)"
        logfile = tmp_path / "testlog"
        runner = CommandRunner(tmp_path, env={})
        log_handler = FileLogHandler(logfile)
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
        """Test that timeout from device config is preferred."""
        self.config["global_timeout"] = 1
        fake_job_data = {"global_timeout": 3}
        job = _TestflingerJob(fake_job_data, client)
        timeout = job.get_global_timeout()
        assert timeout == 1

    def test_job_output_timeout(self, tmp_path):
        """Test that output timeout from job_data is respected."""
        timeout_str = "ERROR: Output timeout reached! (1s)"
        logfile = tmp_path / "testlog"
        runner = CommandRunner(tmp_path, env={})
        log_handler = FileLogHandler(logfile)
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
        """Test that output timeout from device config is preferred."""
        self.config["output_timeout"] = 1
        fake_job_data = {"output_timeout": 3}
        job = _TestflingerJob(fake_job_data, client)
        timeout = job.get_output_timeout()
        assert timeout == 1

    def test_no_output_timeout_in_provision(
        self, client, tmp_path, requests_mock
    ):
        """Test that output timeout is ignored when not in test phase."""
        timeout_str = "complete\n"
        logfile = tmp_path / "provision.log"
        fake_job_data = {"output_timeout": 1, "provision_data": {"url": "foo"}}
        self.config["provision_command"] = (
            "bash -c 'sleep 12 && echo complete'"
        )
        requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)
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
        non-zero value if CommandRunner.run() raises an exception.
        """
        # create the outcome file since we bypassed that
        with open(tmp_path / "testflinger-outcome.json", "w") as outcome_file:
            outcome_file.write("{}")

        self.config["setup_command"] = "fake_setup_command"
        requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)
        requests_mock.get(rmock.ANY, json={}, status_code=HTTPStatus.OK)
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

    @pytest.mark.timeout(1)
    def test_wait_for_completion(self, client):
        """Test that wait_for_completion works."""
        # Make sure we return "completed" for the parent job state
        client.check_job_state = lambda _: "completed"

        job = _TestflingerJob({"parent_job_id": "999"}, client)
        job.wait_for_completion()
        # No assertions needed, just make sure we don't timeout

    def test_get_device_info(self, client, tmp_path):
        """Test job can read from device-info file."""
        # Create device-info.json to simulate device-connector
        fake_device = {"device_ip": "10.10.10.10", "agent_name": "test_agent"}
        with open(tmp_path / "device-info.json", "w") as devinfo_file:
            json.dump(fake_device, devinfo_file)

        fake_job_data = {"output_timeout": 1, "provision_data": {"url": "foo"}}
        job = _TestflingerJob(fake_job_data, client)
        device_info = job.get_device_info(tmp_path)

        # Compare retrieved data with expected data
        assert all(
            device_info[key] == value for key, value in fake_device.items()
        )

    def test_post_device_info_in_reserve(
        self, client, tmp_path, requests_mock
    ):
        """Test device info is sent to results endpoint in reserve phase."""
        # Create device-info.json to simulate device-connector
        fake_device = {"device_ip": "10.10.10.10", "agent_name": "test_agent"}
        with open(tmp_path / "device-info.json", "w") as devinfo_file:
            json.dump(fake_device, devinfo_file)

        # create the outcome file since we bypassed that
        with open(tmp_path / "testflinger-outcome.json", "w") as outcome_file:
            outcome_file.write("{}")

        job_id = str(uuid.uuid1())
        self.config["reserve_command"] = "/bin/true"
        fake_job_data = {
            "global_timeout": 1,
            "reserve_data": {"ssh_keys": "foo"},
            "job_id": job_id,
        }

        post_mock = requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)
        requests_mock.get(rmock.ANY, status_code=HTTPStatus.OK)
        job = _TestflingerJob(fake_job_data, client)
        job.run_test_phase("reserve", tmp_path)

        # Determine the POST request that contains the device info
        device_info_request = None
        for req in post_mock.request_history:
            try:
                req_data = req.json()
                if "device_ip" in req_data or "agent_name" in req_data:
                    device_info_request = req_data
                    break
            except ValueError:
                continue

        assert device_info_request is not None
        # Compare retrieved data with expected data
        assert all(
            device_info_request[key] == value
            for key, value in fake_device.items()
        )

    @pytest.mark.parametrize(
        "phase",
        [
            TestPhase.SETUP,
            TestPhase.PROVISION,
            TestPhase.TEST,
            TestPhase.RESERVE,
        ],
    )
    def test_send_and_store_results(
        self, client, phase, tmp_path, requests_mock
    ):
        """Validate each phase sends results and stores them correctly."""
        self.config[f"{phase}_command"] = "/bin/true"
        fake_job_data = {"global_timeout": 1, f"{phase}_data": {"foo": "foo"}}
        outcome_file_path = tmp_path / "testflinger-outcome.json"

        # create the outcome file since we bypassed that
        with outcome_file_path.open("w") as outcome_file:
            outcome_file.write("{}")

        requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)
        requests_mock.get(rmock.ANY, status_code=HTTPStatus.OK)
        job = _TestflingerJob(fake_job_data, client)
        job.run_test_phase(phase, tmp_path)

        with outcome_file_path.open() as outcome_file:
            outcome_data = json.load(outcome_file)

        # Validate phase status was also sent as POST to the server
        phase_status_request = None
        for req in requests_mock.request_history:
            try:
                req_data = req.json()
                if "status" in req_data and phase in req_data["status"]:
                    phase_status_request = req_data
                    break
            except (ValueError, TypeError):
                continue

        assert phase_status_request is not None
        assert phase_status_request["status"][phase] == 0

        # Validate phase status is stored in outcome file
        assert outcome_data.get("status").get(phase) == 0

    @pytest.mark.parametrize(
        "phase",
        [
            TestPhase.SETUP,
            TestPhase.PROVISION,
            TestPhase.TEST,
            TestPhase.RESERVE,
        ],
    )
    def test_fail_to_send_results(
        self, client, phase, tmp_path, requests_mock
    ):
        """Test results are still stored when sending to server fails."""
        self.config[f"{phase}_command"] = "/bin/true"
        fake_job_data = {"global_timeout": 1, f"{phase}_data": {"foo": "foo"}}
        outcome_file = tmp_path / "testflinger-outcome.json"
        outcome_file.write_text("{}")

        # Simulate server failure by similating 422 response
        requests_mock.post(
            rmock.ANY, status_code=HTTPStatus.UNPROCESSABLE_ENTITY
        )
        requests_mock.get(rmock.ANY, status_code=HTTPStatus.OK)
        job = _TestflingerJob(fake_job_data, client)

        # Should complete without raising exceptions
        exitcode, _, _ = job.run_test_phase(phase, tmp_path)
        assert exitcode == 0

        # Validate phase status is stored in outcome file
        with outcome_file.open() as outcome_f:
            outcome_data = json.load(outcome_f)
        assert outcome_data.get("status").get(phase) == 0

    def test_incremental_status_updates(self, client, tmp_path, requests_mock):
        """Test that cumulative status updates are sent and stored."""
        # Configure multiple phases
        self.config["provision_command"] = "/bin/true"
        self.config["test_command"] = "/bin/true"
        fake_job_data = {
            "global_timeout": 1,
            "provision_data": {"foo": "foo"},
            "test_data": {"bar": "bar"},
        }
        outcome_file_path = tmp_path / "testflinger-outcome.json"
        outcome_file_path.write_text("{}")

        requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)
        requests_mock.get(rmock.ANY, status_code=HTTPStatus.OK)
        job = _TestflingerJob(fake_job_data, client)

        # Run provision phase
        job.run_test_phase(TestPhase.PROVISION, tmp_path)

        # Run test phase
        job.run_test_phase(TestPhase.TEST, tmp_path)

        # Find the POST request for the test phase
        test_phase_request = None
        for req in reversed(requests_mock.request_history):
            try:
                req_data = req.json()
                if (
                    "status" in req_data
                    and TestPhase.TEST in req_data["status"]
                ):
                    test_phase_request = req_data
                    break
            except ValueError:
                continue

        # Verify that the test phase request includes both phase statuses
        assert test_phase_request is not None
        assert TestPhase.PROVISION in test_phase_request["status"]
        assert TestPhase.TEST in test_phase_request["status"]
        assert test_phase_request["status"][TestPhase.PROVISION] == 0
        assert test_phase_request["status"][TestPhase.TEST] == 0

        # Verify outcome file has both statuses
        with outcome_file_path.open() as f:
            outcome_data = json.load(f)
        assert outcome_data["status"][TestPhase.PROVISION] == 0
        assert outcome_data["status"][TestPhase.TEST] == 0

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

    def test_run_test_phase_secret(self, client, tmp_path, requests_mock):
        requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)
        requests_mock.get(rmock.ANY, json={}, status_code=HTTPStatus.OK)

        # create the job data
        job_data = {
            "test_data": {
                "secrets": {"SECRET": "Major"},
                "test_cmds": "echo -n Message: Captain Major $SECRET",
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

    def test_serial_log_to_endpoint(self, client, tmp_path, requests_mock):
        """
        Test that serial log file data are written to the serial log
        endpoint.
        """
        phase = "provision"
        output = "a" * 2048
        serial_log = tmp_path / f"{phase}-serial.log"
        with open(serial_log, "w") as f:
            f.write(output)

        # create the outcome file since we bypassed that
        with open(tmp_path / "testflinger-outcome.json", "w") as outcome_file:
            outcome_file.write("{}")

        job_id = str(uuid.uuid1())
        fake_job_data = {
            "job_id": job_id,
            "output_timeout": 1,
            f"{phase}_data": {"url": "foo"},
        }

        job = _TestflingerJob(fake_job_data, client)
        self.config[f"{phase}_command"] = "/bin/true"
        requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)
        return_value, exit_event, exit_reason = job.run_test_phase(
            phase, tmp_path
        )
        serial_url = f"http://127.0.0.1:8000/v1/result/{job_id}/log/serial"
        requests = list(
            filter(
                lambda req: req.url == serial_url,
                requests_mock.request_history,
            )
        )
        assert len(requests) == 2
        for i in range(2):
            assert requests[i].json()["fragment_number"] == i
            assert requests[i].json()["phase"] == phase
            assert requests[i].json()["log_data"] == "a" * 1024
