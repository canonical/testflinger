import json
import os
from pathlib import Path
import re
import shutil
import tarfile
import tempfile
import uuid
import requests_mock as rmock
import pytest

from mock import patch

import testflinger_agent
from testflinger_agent.agent import TestflingerAgent as _TestflingerAgent
from testflinger_agent.client import TestflingerClient as _TestflingerClient
from testflinger_agent.config import ATTACHMENTS_DIR
from testflinger_agent.errors import TFServerError
from testflinger_agent.job import TestflingerJob, JobPhaseResult
from testflinger_common.enums import TestEvent


class TestClient:
    @pytest.fixture
    def agent(self, requests_mock):
        self.tmpdir = tempfile.mkdtemp()
        self.config = {
            "agent_id": "test01",
            "identifier": "12345-123456",
            "polling_interval": "2",
            "server_address": "127.0.0.1:8000",
            "job_queues": ["test"],
            "location": "nowhere",
            "provision_type": "noprovision",
            "execution_basedir": self.tmpdir,
            "logging_basedir": self.tmpdir,
            "results_basedir": os.path.join(self.tmpdir, "results"),
            "test_string": "ThisIsATest",
        }
        testflinger_agent.configure_logging(self.config)
        client = _TestflingerClient(self.config)
        requests_mock.get(rmock.ANY)
        requests_mock.post(rmock.ANY)
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

    def test_attachments(self, agent, tmp_path):
        # create file to be used as attachment
        attachment = tmp_path / "random.bin"
        attachment.write_bytes(os.urandom(128))
        # create gzipped archive containing attachment
        archive = tmp_path / "attachments.tar.gz"
        archive_name = "test/random.bin"
        with tarfile.open(archive, "w:gz") as attachments:
            attachments.add(attachment, arcname=archive_name)
        # job data specifies how the attachment will be handled
        job_id = str(uuid.uuid1())
        mock_job_data = {
            "job_id": job_id,
            "job_queue": "test",
            "test_data": {
                "attachments": [
                    {
                        "local": str(attachment),
                        "agent": str(attachment.name),
                    }
                ]
            },
            "attachments_status": "complete",
        }

        with rmock.Mocker() as mocker:
            mocker.post(rmock.ANY, status_code=200)
            # mock response to requesting jobs
            mocker.get(
                re.compile(r"/v1/job\?queue=\w+"),
                [{"text": json.dumps(mock_job_data)}, {"text": "{}"}],
            )
            # mock response to requesting job attachments
            mocker.get(
                re.compile(r"/v1/job/[-a-z0-9]+/attachments"),
                content=archive.read_bytes(),
            )
            # mock response to results request
            mocker.get(re.compile(r"/v1/result/"))

            # request and process the job (should unpack the archive)
            with patch("shutil.rmtree"):
                agent.process_jobs()

            # check the request history to confirm that:
            # - there is a request to the job retrieval endpoint
            # - there a request to the attachment retrieval endpoint
            history = mocker.request_history
            assert history[0].path == "/v1/job"
            assert history[2].path == f"/v1/job/{job_id}/attachments"

            # check that the attachment is where it's supposed to be
            basepath = Path(self.tmpdir) / mock_job_data["job_id"]
            attachment = basepath / ATTACHMENTS_DIR / archive_name
            assert attachment.exists()

    def test_attachments_insecure_no_phase(self, agent, tmp_path):
        # create file to be used as attachment
        attachment = tmp_path / "random.bin"
        attachment.write_bytes(os.urandom(128))
        # create gzipped archive containing attachment
        archive = tmp_path / "attachments.tar.gz"
        # note: archive name should be under a phase folder
        archive_name = "random.bin"
        with tarfile.open(archive, "w:gz") as attachments:
            attachments.add(attachment, arcname=archive_name)
        # job data specifies how the attachment will be handled
        job_id = str(uuid.uuid1())
        mock_job_data = {
            "job_id": job_id,
            "job_queue": "test",
            "test_data": {
                "attachments": [
                    {
                        "local": str(attachment),
                        "agent": str(attachment.name),
                    }
                ]
            },
            "attachments_status": "complete",
        }

        with rmock.Mocker() as mocker:
            mocker.post(rmock.ANY, status_code=200)
            # mock response to requesting jobs
            mocker.get(
                re.compile(r"/v1/job\?queue=\w+"),
                [{"text": json.dumps(mock_job_data)}, {"text": "{}"}],
            )
            # mock response to requesting job attachments
            mocker.get(
                re.compile(r"/v1/job/[-a-z0-9]+/attachments"),
                content=archive.read_bytes(),
            )
            # mock response to results request
            mocker.get(re.compile(r"/v1/result/"))

            # request and process the job (should unpack the archive)
            with patch("shutil.rmtree"):
                agent.process_jobs()

            # check the request history to confirm that:
            # - there is a request to the job retrieval endpoint
            # - there a request to the attachment retrieval endpoint
            history = mocker.request_history
            assert history[0].path == "/v1/job"
            assert history[2].path == f"/v1/job/{job_id}/attachments"

            # check that the attachment is *not* where it's supposed to be
            basepath = Path(self.tmpdir) / mock_job_data["job_id"]
            attachment = basepath / ATTACHMENTS_DIR / archive_name
            assert not attachment.exists()

    def test_attachments_insecure_out_of_hierarchy(self, agent, tmp_path):
        # create file to be used as attachment
        attachment = tmp_path / "random.bin"
        attachment.write_bytes(os.urandom(128))
        # create gzipped archive containing attachment
        archive = tmp_path / "attachments.tar.gz"
        # note: archive name should be under a phase folder
        archive_name = "test/../random.bin"
        with tarfile.open(archive, "w:gz") as attachments:
            attachments.add(attachment, arcname=archive_name)
        # job data specifies how the attachment will be handled
        job_id = str(uuid.uuid1())
        mock_job_data = {
            "job_id": job_id,
            "job_queue": "test",
            "test_data": {
                "attachments": [
                    {
                        "local": str(attachment),
                        "agent": str(attachment.name),
                    }
                ]
            },
            "attachments_status": "complete",
        }

        with rmock.Mocker() as mocker:
            mocker.post(rmock.ANY, status_code=200)
            # mock response to requesting jobs
            mocker.get(
                re.compile(r"/v1/job\?queue=\w+"),
                [{"text": json.dumps(mock_job_data)}, {"text": "{}"}],
            )
            # mock response to requesting job attachments
            mocker.get(
                re.compile(r"/v1/job/[-a-z0-9]+/attachments"),
                content=archive.read_bytes(),
            )
            # mock response to results request
            mocker.get(re.compile(r"/v1/result/"))

            # request and process the job (should unpack the archive)
            with patch("shutil.rmtree"):
                agent.process_jobs()

            # check the request history to confirm that:
            # - there is a request to the job retrieval endpoint
            # - there a request to the attachment retrieval endpoint
            history = mocker.request_history
            assert history[0].path == "/v1/job"
            assert history[2].path == f"/v1/job/{job_id}/attachments"

            # check that the attachment is *not* where it's supposed to be
            basepath = Path(self.tmpdir) / mock_job_data["job_id"]
            attachment = basepath / ATTACHMENTS_DIR / archive_name
            assert not attachment.exists()

    def test_config_vars_in_env(self, agent, requests_mock):
        self.config["test_command"] = (
            "bash -c 'echo test_string is $test_string'"
        )
        mock_job_data = {
            "job_id": str(uuid.uuid1()),
            "job_queue": "test",
            "test_data": {"test_cmds": "foo"},
        }
        requests_mock.get(
            rmock.ANY, [{"text": json.dumps(mock_job_data)}, {"text": "{}"}]
        )
        requests_mock.post(rmock.ANY, status_code=200)
        with patch("shutil.rmtree"):
            agent.process_jobs()
        testlog = open(
            os.path.join(self.tmpdir, mock_job_data.get("job_id"), "test.log")
        ).read()
        assert "ThisIsATest" in testlog

    def test_phase_failed(self, agent, requests_mock):
        # Make sure we stop running after a failed phase
        self.config["provision_command"] = "/bin/false"
        self.config["test_command"] = "echo test1"
        mock_job_data = {
            "job_id": str(uuid.uuid1()),
            "job_queue": "test",
            "provision_data": {"url": "foo"},
            "test_data": {"test_cmds": "foo"},
        }
        requests_mock.get(
            rmock.ANY, [{"text": json.dumps(mock_job_data)}, {"text": "{}"}]
        )
        requests_mock.post(rmock.ANY, status_code=200)
        with patch("shutil.rmtree"), patch("os.unlink"):
            agent.process_jobs()
        outcome_file = os.path.join(
            os.path.join(
                self.tmpdir,
                mock_job_data.get("job_id"),
                "testflinger-outcome.json",
            )
        )
        with open(outcome_file) as f:
            outcome_data = json.load(f)
        assert outcome_data.get("provision_status") == 1
        assert outcome_data.get("test_status") is None

    def test_phase_timeout(self, agent, requests_mock):
        # Make sure the status code of a timed-out phase is correct
        self.config["test_command"] = "sleep 12"
        mock_job_data = {
            "job_id": str(uuid.uuid1()),
            "job_queue": "test",
            "output_timeout": 1,
            "test_data": {"test_cmds": "foo"},
        }
        requests_mock.get(
            rmock.ANY, [{"text": json.dumps(mock_job_data)}, {"text": "{}"}]
        )
        requests_mock.post(rmock.ANY, status_code=200)
        with patch("shutil.rmtree"), patch("os.unlink"):
            agent.process_jobs()
        outcome_file = os.path.join(
            os.path.join(
                self.tmpdir,
                mock_job_data.get("job_id"),
                "testflinger-outcome.json",
            )
        )
        with open(outcome_file) as f:
            outcome_data = json.load(f)
        assert outcome_data.get("test_status") == 247

    def test_retry_transmit(self, agent, requests_mock):
        # Make sure we retry sending test results
        self.config["provision_command"] = "/bin/false"
        self.config["test_command"] = "echo test1"
        mock_job_data = {"job_id": str(uuid.uuid1()), "job_queue": "test"}
        # Send an extra empty data since we will be calling get 3 times
        requests_mock.get(
            rmock.ANY,
            [
                {"text": json.dumps(mock_job_data)},
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
                mock_job_data.get("job_id"),
            )
            mock_transmit_job_outcome.assert_called_with(first_dir)
            # Try processing jobs again, now it should be in results_basedir
            agent.process_jobs()
            retry_dir = os.path.join(
                self.config.get("results_basedir"), mock_job_data.get("job_id")
            )
            mock_transmit_job_outcome.assert_called_with(retry_dir)

    def test_recovery_failed(self, agent, requests_mock):
        # Make sure we stop processing jobs after a device recovery error
        OFFLINE_FILE = "/tmp/TESTFLINGER-DEVICE-OFFLINE-test001"
        if os.path.exists(OFFLINE_FILE):
            os.unlink(OFFLINE_FILE)
        self.config["agent_id"] = "test001"
        self.config["provision_command"] = "bash -c 'exit 46'"
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
            m.post(
                "http://127.0.0.1:8000/v1/agents/data/"
                + self.config.get("agent_id"),
                text="OK",
            )

            agent.process_jobs()
            assert agent.check_offline()
        if os.path.exists(OFFLINE_FILE):
            os.unlink(OFFLINE_FILE)

    def test_post_agent_data(self, agent):
        # Make sure we post the initial agent data
        with patch.object(
            testflinger_agent.client.TestflingerClient, "post_agent_data"
        ) as mock_post_agent_data:
            agent._post_initial_agent_data()
            mock_post_agent_data.assert_called_with(
                {
                    "identifier": self.config["identifier"],
                    "queues": self.config["job_queues"],
                    "location": self.config["location"],
                    "provision_type": self.config["provision_type"],
                }
            )

    def test_post_agent_status_update(self, agent, requests_mock):
        self.config["test_command"] = "echo test1"
        job_id = str(uuid.uuid1())
        fake_job_data = {
            "job_id": job_id,
            "job_queue": "test",
            "test_data": {"test_cmds": "foo"},
            "job_status_webhook": "https://mywebhook",
        }
        requests_mock.get(
            "http://127.0.0.1:8000/v1/job?queue=test",
            [{"text": json.dumps(fake_job_data)}, {"text": "{}"}],
        )
        status_url = f"http://127.0.0.1:8000/v1/job/{job_id}/events"
        requests_mock.post(status_url, status_code=200)
        with patch("shutil.rmtree"):
            agent.process_jobs()

        status_update_requests = list(
            filter(
                lambda req: req.url == status_url,
                requests_mock.request_history,
            )
        )
        event_list = status_update_requests[-1].json()["events"]
        event_name_list = [event["event_name"] for event in event_list]
        expected_event_name_list = [
            phase.value + postfix
            for phase in TestflingerJob.phase_sequence
            for postfix in ["_start", "_success"]
            if f"{phase}_data" in fake_job_data
            and f"{phase}_command" in self.config
        ]
        expected_event_name_list.insert(0, "job_start")
        expected_event_name_list.append("job_end")

        assert event_list[-1]["detail"] == "normal_exit"
        assert event_name_list == expected_event_name_list

    def test_post_agent_status_update_cancelled(self, agent, requests_mock):
        self.config["test_command"] = "echo test1"
        job_id = str(uuid.uuid1())
        fake_job_data = {
            "job_id": job_id,
            "job_queue": "test",
            "test_data": {"test_cmds": "foo"},
            "job_status_webhook": "https://mywebhook",
        }
        requests_mock.get(
            "http://127.0.0.1:8000/v1/job?queue=test",
            [{"text": json.dumps(fake_job_data)}, {"text": "{}"}],
        )
        status_url = f"http://127.0.0.1:8000/v1/job/{job_id}/events"
        requests_mock.post(status_url, status_code=200)

        requests_mock.get(
            "http://127.0.0.1:8000/v1/result/" + job_id,
            json={"job_state": "cancelled"},
        )
        with patch("shutil.rmtree"):
            agent.process_jobs()

        status_update_requests = list(
            filter(
                lambda req: req.url == status_url,
                requests_mock.request_history,
            )
        )
        event_list = status_update_requests[-1].json()["events"]
        event_name_list = [event["event_name"] for event in event_list]

        assert "cancelled" in event_name_list

    def test_post_agent_status_update_global_timeout(
        self, agent, requests_mock
    ):
        self.config["test_command"] = "sleep 12"
        job_id = str(uuid.uuid1())
        fake_job_data = {
            "job_id": job_id,
            "job_queue": "test",
            "test_data": {"test_cmds": "foo"},
            "job_status_webhook": "https://mywebhook",
            "global_timeout": 1,
        }
        requests_mock.get(
            "http://127.0.0.1:8000/v1/job?queue=test",
            [{"text": json.dumps(fake_job_data)}, {"text": "{}"}],
        )
        status_url = f"http://127.0.0.1:8000/v1/job/{job_id}/events"
        requests_mock.post(status_url, status_code=200)

        with patch("shutil.rmtree"):
            agent.process_jobs()

        status_update_requests = list(
            filter(
                lambda req: req.url == status_url,
                requests_mock.request_history,
            )
        )
        event_list = status_update_requests[-1].json()["events"]
        event_name_list = [event["event_name"] for event in event_list]

        assert "global_timeout" in event_name_list

    def test_post_agent_status_update_output_timeout(
        self, agent, requests_mock
    ):
        self.config["test_command"] = "sleep 12"
        job_id = str(uuid.uuid1())
        fake_job_data = {
            "job_id": job_id,
            "job_queue": "test",
            "test_data": {"test_cmds": "foo"},
            "job_status_webhook": "https://mywebhook",
            "output_timeout": 1,
        }
        requests_mock.get(
            "http://127.0.0.1:8000/v1/job?queue=test",
            [{"text": json.dumps(fake_job_data)}, {"text": "{}"}],
        )
        status_url = f"http://127.0.0.1:8000/v1/job/{job_id}/events"
        requests_mock.post(status_url, status_code=200)

        with patch("shutil.rmtree"):
            agent.process_jobs()

        status_update_requests = list(
            filter(
                lambda req: req.url == status_url,
                requests_mock.request_history,
            )
        )
        event_list = status_update_requests[-1].json()["events"]
        event_name_list = [event["event_name"] for event in event_list]
        assert "output_timeout" in event_name_list

    def test_post_provision_log_success(self, agent, requests_mock):
        # Ensure provision log is posted when the provision phase succeeds
        self.config["provision_command"] = "echo provision1"
        job_id = str(uuid.uuid1())
        fake_job_data = {
            "job_id": job_id,
            "job_queue": "test",
            "provision_data": {"url": "foo"},
        }
        requests_mock.get(
            "http://127.0.0.1:8000/v1/job?queue=test",
            [{"text": json.dumps(fake_job_data)}, {"text": "{}"}],
        )
        expected_log_params = (
            job_id,
            0,
            TestEvent.PROVISION_SUCCESS,
        )
        with patch.object(
            agent.client, "post_provision_log"
        ) as mock_post_provision_log:
            agent.process_jobs()
            mock_post_provision_log.assert_called_with(*expected_log_params)

    def test_post_provision_log_fail(self, agent, requests_mock):
        # Ensure provision log is posted when the provision phase fails
        self.config["provision_command"] = "exit 1"
        job_id = str(uuid.uuid1())
        fake_job_data = {
            "job_id": job_id,
            "job_queue": "test",
            "provision_data": {"url": "foo"},
        }
        requests_mock.get(
            "http://127.0.0.1:8000/v1/job?queue=test",
            [{"text": json.dumps(fake_job_data)}, {"text": "{}"}],
        )
        expected_log_params = (
            job_id,
            1,
            TestEvent.PROVISION_FAIL,
        )
        with patch.object(
            agent.client, "post_provision_log"
        ) as mock_post_provision_log:
            agent.process_jobs()
            mock_post_provision_log.assert_called_with(*expected_log_params)

    def test_provision_error_in_event_detail(self, agent, requests_mock):
        """Tests provision log error messages in event log detail field"""
        self.config["provision_command"] = "echo provision1"
        job_id = str(uuid.uuid1())
        fake_job_data = {
            "job_id": job_id,
            "job_queue": "test",
            "provision_data": {"url": "foo"},
            "job_status_webhook": "https://mywebhook",
        }
        requests_mock.get(
            "http://127.0.0.1:8000/v1/job?queue=test",
            [{"text": json.dumps(fake_job_data)}, {"text": "{}"}],
        )
        status_url = f"http://127.0.0.1:8000/v1/job/{job_id}/events"
        requests_mock.post(status_url, status_code=200)

        provision_exception_info = {
            "provision_exception_info": {
                "exception_name": "MyExceptionName",
                "exception_message": "MyExceptionMessage",
                "exception_cause": "MyExceptionCause",
            }
        }

        def run_core_provision_patch(self):
            provision_log_path = (
                self.params.rundir / "device-connector-error.json"
            )
            with open(provision_log_path, "w") as provision_log_file:
                provision_log_file.write(json.dumps(provision_exception_info))
            self.result = JobPhaseResult(
                exit_code=99,
                event=f"{self.phase_id}_fail",
                detail=self.parse_error_logs(),
            )

        with patch("shutil.rmtree"):
            with patch(
                "testflinger_agent.job.ProvisionPhase.run",
                run_core_provision_patch,
            ):
                agent.process_jobs()

        status_update_requests = list(
            filter(
                lambda req: req.url == status_url,
                requests_mock.request_history,
            )
        )
        event_list = status_update_requests[-1].json()["events"]
        provision_fail_events = list(
            filter(
                lambda event: event["event_name"] == "provision_fail",
                event_list,
            )
        )
        assert len(provision_fail_events) == 1
        provision_fail_event_detail = provision_fail_events[0]["detail"]
        assert (
            provision_fail_event_detail
            == "MyExceptionName: MyExceptionMessage caused by MyExceptionCause"
        )

    def test_provision_error_no_cause(self, agent, requests_mock):
        """Tests provision log error messages for exceptions with no cause"""
        self.config["provision_command"] = "echo provision1"
        job_id = str(uuid.uuid1())
        fake_job_data = {
            "job_id": job_id,
            "job_queue": "test",
            "provision_data": {"url": "foo"},
            "job_status_webhook": "https://mywebhook",
        }
        requests_mock.get(
            "http://127.0.0.1:8000/v1/job?queue=test",
            [{"text": json.dumps(fake_job_data)}, {"text": "{}"}],
        )
        status_url = f"http://127.0.0.1:8000/v1/job/{job_id}/events"
        requests_mock.post(status_url, status_code=200)

        provision_exception_info = {
            "provision_exception_info": {
                "exception_name": "MyExceptionName",
                "exception_message": "MyExceptionMessage",
                "exception_cause": None,
            }
        }

        def run_core_provision_patch(self):
            provision_log_path = (
                self.params.rundir / "device-connector-error.json"
            )
            with open(provision_log_path, "w") as provision_log_file:
                provision_log_file.write(json.dumps(provision_exception_info))
            self.result = JobPhaseResult(
                exit_code=99,
                event=f"{self.phase_id}_fail",
                detail=self.parse_error_logs(),
            )

        with patch("shutil.rmtree"):
            with patch(
                "testflinger_agent.job.ProvisionPhase.run",
                run_core_provision_patch,
            ):
                agent.process_jobs()

        status_update_requests = list(
            filter(
                lambda req: req.url == status_url,
                requests_mock.request_history,
            )
        )
        event_list = status_update_requests[-1].json()["events"]
        provision_fail_events = list(
            filter(
                lambda event: event["event_name"] == "provision_fail",
                event_list,
            )
        )
        assert len(provision_fail_events) == 1
        provision_fail_event_detail = provision_fail_events[0]["detail"]
        assert (
            provision_fail_event_detail
            == "MyExceptionName: MyExceptionMessage"
        )
