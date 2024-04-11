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
from testflinger_agent.config import ATTACHMENTS_DIR
from testflinger_agent.errors import TFServerError
from testflinger_agent.client import TestflingerClient as _TestflingerClient
from testflinger_agent.agent import TestflingerAgent as _TestflingerAgent


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
        with tarfile.open(archive, "w:gz") as attachments:
            attachments.add(attachment, arcname=f"test/{attachment}")
        # job data specifies how the attachment will be handled
        fake_job_data = {
            "job_id": str(uuid.uuid1()),
            "job_queue": "test",
            "test_data": {
                "attachments": [
                    {
                        "local": str(attachment),
                        "agent": str(attachment.name),
                    }
                ]
            },
            "attachments": "complete",
        }

        with rmock.Mocker() as mocker:
            mocker.post(rmock.ANY, status_code=200)
            # mock response to requesting jobs
            mocker.get(
                re.compile(r"/v1/job\?queue=\w+"),
                [{"text": json.dumps(fake_job_data)}, {"text": "{}"}],
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

            # check that the attachment is where it's supposed to be
            basepath = Path(self.tmpdir) / fake_job_data["job_id"]
            attachment = basepath / ATTACHMENTS_DIR / "test" / attachment.name
            assert attachment.exists()

    def test_config_vars_in_env(self, agent, requests_mock):
        self.config["test_command"] = (
            "bash -c 'echo test_string is $test_string'"
        )
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
