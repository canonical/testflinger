# Copyright (C) 2016 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import json
import os
import re
import shutil
import tarfile
import tempfile
import uuid
from http import HTTPStatus
from pathlib import Path
from unittest.mock import patch

import prometheus_client
import pytest
import requests
import requests_mock as rmock
from testflinger_common.enums import (
    AgentMode,
    AgentState,
    LogType,
    TestEvent,
    TestPhase,
)

import testflinger_agent
from testflinger_agent.agent import TestflingerAgent as _TestflingerAgent
from testflinger_agent.client import TestflingerClient as _TestflingerClient
from testflinger_agent.config import ATTACHMENTS_DIR
from testflinger_agent.errors import TFServerError
from testflinger_agent.schema import validate


class TestClient:
    """Test agent client behavior.

    Note on v2 Contract: Most mocks provide agent data with 'mode' and 'state'
    fields. These are INFORMATIONAL (what agent last reported). Agent does NOT
    change based on these. Agent only changes mode via 'commanded_mode' from
    admin. Tests without 'commanded_mode' test normal agent operation.
    """

    @pytest.fixture(autouse=True)
    def clear_registry(self):
        """
        Clear Prometheus metrics so they don't get duplicated across
        test runs.
        """
        collectors = tuple(
            prometheus_client.REGISTRY._collector_to_names.keys()
        )
        for collector in collectors:
            prometheus_client.REGISTRY.unregister(collector)
        yield

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
                "links": [
                    {"url": "https://testurl.com", "label": "Test Label"}
                ],
            }
        )
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
            f"http://127.0.0.1:8000/v2/agents/{self.config['agent_id']}/data",
            json={"mode": "online", "state": "waiting", "restricted_to": {}},
        )
        requests_mock.get(
            "http://127.0.0.1:8000/v1/job?queue=test",
            [{"text": json.dumps(fake_job_data)}, {"text": "{}"}],
        )
        requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)
        with patch("shutil.rmtree"):
            agent.process_one_job()
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
            f"http://127.0.0.1:8000/v2/agents/{self.config['agent_id']}/data",
            json={"mode": "online", "state": "waiting", "restricted_to": {}},
        )
        requests_mock.get(
            "http://127.0.0.1:8000/v1/job?queue=test",
            [{"text": json.dumps(fake_job_data)}, {"text": "{}"}],
        )
        requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)
        with patch("shutil.rmtree"):
            agent.process_one_job()
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
            f"http://127.0.0.1:8000/v2/agents/{self.config['agent_id']}/data",
            json={"mode": "online", "state": "waiting", "restricted_to": {}},
        )
        requests_mock.get(
            "http://127.0.0.1:8000/v1/job?queue=test",
            [{"text": json.dumps(fake_job_data)}, {"text": "{}"}],
        )
        requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)
        with patch("shutil.rmtree"):
            agent.process_one_job()
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
            mocker.post(rmock.ANY, status_code=HTTPStatus.OK)
            # mock response to requesting jobs
            mocker.get(f"{agent.client.server}/v1", status_code=HTTPStatus.OK)
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
            # mock response to requesting agent data
            mocker.get(
                "http://127.0.0.1:8000/v2/agents/test01/data",
                json={
                    "mode": "online",
                    "state": "waiting",
                    "restricted_to": {},
                },
            )

            # request and process the job (should unpack the archive)
            with patch("shutil.rmtree"):
                agent.process_one_job()

            # check the request history to confirm that:
            # - there is a request to the job retrieval endpoint
            # - there a request to the attachment retrieval endpoint
            history = mocker.request_history
            request_paths = [req.path for req in history]
            assert "/v1/job" in request_paths
            assert f"/v1/job/{job_id}/attachments" in request_paths

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
            mocker.post(rmock.ANY, status_code=HTTPStatus.OK)
            # mock response to requesting jobs
            mocker.get(f"{agent.client.server}/v1", status_code=HTTPStatus.OK)
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
            mocker.get(
                "http://127.0.0.1:8000/v2/agents/test01/data",
                json={
                    "mode": "online",
                    "state": "waiting",
                    "restricted_to": {},
                },
            )

            # request and process the job (should unpack the archive)
            with patch("shutil.rmtree"):
                agent.process_one_job()

            # check the request history to confirm that:
            # - there is a request to the job retrieval endpoint
            # - there a request to the attachment retrieval endpoint
            history = mocker.request_history
            request_paths = [req.path for req in history]
            assert "/v1/job" in request_paths
            assert f"/v1/job/{job_id}/attachments" in request_paths

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
            mocker.post(rmock.ANY, status_code=HTTPStatus.OK)
            # mock response to requesting jobs
            mocker.get(f"{agent.client.server}/v1", status_code=HTTPStatus.OK)
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
            mocker.get(
                "http://127.0.0.1:8000/v2/agents/test01/data",
                json={
                    "mode": "online",
                    "state": "waiting",
                    "restricted_to": {},
                },
            )

            # request and process the job (should unpack the archive)
            with patch("shutil.rmtree"):
                agent.process_one_job()

            # check the request history to confirm that:
            # - there is a request to the job retrieval endpoint
            # - there a request to the attachment retrieval endpoint
            history = mocker.request_history
            request_paths = [req.path for req in history]
            assert "/v1/job" in request_paths
            assert f"/v1/job/{job_id}/attachments" in request_paths

            # check that the attachment is *not* where it's supposed to be
            basepath = Path(self.tmpdir) / mock_job_data["job_id"]
            attachment = basepath / ATTACHMENTS_DIR / archive_name
            assert not attachment.exists()

    def test_config_vars_in_env(self, agent, requests_mock):
        self.config["test_command"] = "bash -c 'echo agent_id is $agent_id'"
        mock_job_data = {
            "job_id": str(uuid.uuid1()),
            "job_queue": "test",
            "test_data": {"test_cmds": "foo"},
        }
        requests_mock.get(
            f"http://127.0.0.1:8000/v2/agents/{self.config['agent_id']}/data",
            json={"mode": "online", "state": "waiting", "restricted_to": {}},
        )
        requests_mock.get(
            "http://127.0.0.1:8000/v1/job?queue=test",
            [{"text": json.dumps(mock_job_data)}, {"text": "{}"}],
        )
        requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)
        with patch("shutil.rmtree"):
            agent.process_one_job()
        testlog = open(
            os.path.join(self.tmpdir, mock_job_data.get("job_id"), "test.log")
        ).read()
        assert self.config["agent_id"] in testlog

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
            f"http://127.0.0.1:8000/v2/agents/{self.config['agent_id']}/data",
            json={"mode": "online", "state": "waiting", "restricted_to": {}},
        )
        requests_mock.get(
            "http://127.0.0.1:8000/v1/job?queue=test",
            [{"text": json.dumps(mock_job_data)}, {"text": "{}"}],
        )
        requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)
        with patch("shutil.rmtree"), patch("pathlib.Path.unlink"):
            agent.process_one_job()
        outcome_file = os.path.join(
            os.path.join(
                self.tmpdir,
                mock_job_data.get("job_id"),
                "testflinger-outcome.json",
            )
        )
        with open(outcome_file) as f:
            outcome_data = json.load(f)
        assert outcome_data.get("status").get("provision") == 1
        assert outcome_data.get("status").get("test") is None

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
            f"http://127.0.0.1:8000/v2/agents/{self.config['agent_id']}/data",
            json={"mode": "online", "state": "waiting", "restricted_to": {}},
        )
        requests_mock.get(
            "http://127.0.0.1:8000/v1/job?queue=test",
            [{"text": json.dumps(mock_job_data)}, {"text": "{}"}],
        )
        requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)
        with patch("shutil.rmtree"), patch("pathlib.Path.unlink"):
            agent.process_one_job()
        outcome_file = os.path.join(
            os.path.join(
                self.tmpdir,
                mock_job_data.get("job_id"),
                "testflinger-outcome.json",
            )
        )
        with open(outcome_file) as f:
            outcome_data = json.load(f)
        assert outcome_data.get("status").get("test") == 247

    def test_retry_transmit(self, agent, requests_mock):
        # Make sure we retry sending test results
        self.config["provision_command"] = "/bin/false"
        self.config["test_command"] = "echo test1"
        mock_job_data = {"job_id": str(uuid.uuid1()), "job_queue": "test"}
        requests_mock.get(
            "http://127.0.0.1:8000/v1/job?queue=test",
            [
                {"text": json.dumps(mock_job_data)},
                {"text": "{}"},
            ],
        )
        requests_mock.get(
            f"http://127.0.0.1:8000/v2/agents/{self.config['agent_id']}/data",
            json={
                "commanded_mode": {
                    "value": "online",
                    "changed_at": "2026-10-18T00:00:00",
                    "changed_by": "testflinger@example.com",
                    "comment": "",
                },
                "state": "waiting",
                "restricted_to": {},
            },
        )
        requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)
        with patch.object(
            testflinger_agent.client.TestflingerClient, "transmit_job_outcome"
        ) as mock_transmit_job_outcome:
            # Make sure we fail the first time when transmitting the results
            mock_transmit_job_outcome.side_effect = [TFServerError(404), ""]
            agent.process_one_job()
            first_dir = Path(
                self.config.get("execution_basedir")
            ) / mock_job_data.get("job_id")
            mock_transmit_job_outcome.assert_called_with(first_dir)
            # Try retrying old results, now it should be in results_basedir
            agent.retry_old_results()
            retry_dir = Path(
                self.config.get("results_basedir")
            ) / mock_job_data.get("job_id")
            mock_transmit_job_outcome.assert_called_with(retry_dir)

    def test_recovery_failed(self, agent, requests_mock):
        """Agent enters maintenance mode when recovery fails (exit code 46).

        When the provision phase exits with code 46, the agent detects this
        as an unrecoverable failure and immediately enters maintenance mode.
        This is a self-initiated mode change (not commanded by server).
        """
        self.config["provision_command"] = "bash -c 'exit 46'"
        self.config["test_command"] = "echo test1"
        job_id = str(uuid.uuid1())
        fake_job_data = {
            "job_id": job_id,
            "job_queue": "test",
            "provision_data": {"url": "foo"},
            "test_data": {"test_cmds": "foo"},
        }
        with rmock.Mocker() as m:
            m.get(f"{agent.client.server}/v1", status_code=HTTPStatus.OK)
            m.get(
                "http://127.0.0.1:8000/v1/job?queue=test", json=fake_job_data
            )
            m.get(f"http://127.0.0.1:8000/v1/result/{job_id}", text="{}")
            m.get(
                f"http://127.0.0.1:8000/v1/result/{job_id}/status",
                json={"job_state": "waiting"},
            )
            m.post(f"http://127.0.0.1:8000/v1/result/{job_id}", text="{}")
            m.post(
                f"http://127.0.0.1:8000/v1/result/{job_id}/log/{LogType.STANDARD_OUTPUT}",
                text="{}",
            )
            m.post(
                f"http://127.0.0.1:8000/v2/agents/{self.config.get('agent_id')}/data",
                text="OK",
            )
            m.get(
                f"http://127.0.0.1:8000/v2/agents/{self.config.get('agent_id')}/data",
                json={
                    "commanded_mode": {
                        "value": "online",
                        "changed_at": "2026-10-18T00:00:00",
                        "changed_by": "testflinger@example.com",
                        "comment": "",
                    },
                    "state": "waiting",
                    "restricted_to": {},
                },
            )

            # Mock run_test_phase to return exit code 46 for provision phase
            with patch("shutil.rmtree"):
                with patch(
                    "testflinger_agent.agent.TestflingerJob.run_test_phase"
                ) as mock_run_test_phase:

                    def run_test_phase_side_effect(phase, rundir):
                        if phase == TestPhase.PROVISION:
                            # Create error log file
                            error_log_path = (
                                Path(rundir) / "device-connector-error.json"
                            )
                            error_log_path.write_text(
                                json.dumps({"error": "recovery failed"})
                            )
                            return (
                                46,
                                TestEvent.RECOVERY_FAIL,
                                "Recovery failed",
                            )
                        else:
                            return 0, None, ""

                    mock_run_test_phase.side_effect = (
                        run_test_phase_side_effect
                    )

                    # Process job with recovery failure
                    agent.process_one_job()

            # Verify agent entered maintenance mode due to recovery failure
            assert agent.current_mode == AgentMode.MAINTENANCE, (
                "Agent should enter maintenance mode after recovery failure"
            )

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
                    "links": self.config["links"],
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
        requests_mock.get(
            f"http://127.0.0.1:8000/v2/agents/{self.config['agent_id']}/data",
            json={"mode": "online", "state": "waiting", "restricted_to": {}},
        )
        status_url = f"http://127.0.0.1:8000/v1/job/{job_id}/events"
        requests_mock.post(status_url, status_code=HTTPStatus.OK)
        with patch("shutil.rmtree"):
            agent.process_one_job()

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
            for phase in TestPhase
            for postfix in ["_start", "_success"]
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
        requests_mock.get(
            f"http://127.0.0.1:8000/v2/agents/{self.config['agent_id']}/data",
            json={"mode": "online", "state": "waiting", "restricted_to": {}},
        )
        status_url = f"http://127.0.0.1:8000/v1/job/{job_id}/events"
        requests_mock.post(status_url, status_code=HTTPStatus.OK)

        requests_mock.get(
            f"http://127.0.0.1:8000/v1/result/{job_id}/status",
            json={"job_state": "cancelled"},
        )
        with patch("shutil.rmtree"):
            agent.process_one_job()

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
        requests_mock.get(
            f"http://127.0.0.1:8000/v2/agents/{self.config['agent_id']}/data",
            json={"mode": "online", "state": "waiting", "restricted_to": {}},
        )
        status_url = f"http://127.0.0.1:8000/v1/job/{job_id}/events"
        requests_mock.post(status_url, status_code=HTTPStatus.OK)

        with patch("shutil.rmtree"):
            agent.process_one_job()

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
        requests_mock.get(
            f"http://127.0.0.1:8000/v2/agents/{self.config['agent_id']}/data",
            json={"mode": "online", "state": "waiting", "restricted_to": {}},
        )
        status_url = f"http://127.0.0.1:8000/v1/job/{job_id}/events"
        requests_mock.post(status_url, status_code=HTTPStatus.OK)

        with patch("shutil.rmtree"):
            agent.process_one_job()

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
        requests_mock.get(
            f"http://127.0.0.1:8000/v2/agents/{self.config['agent_id']}/data",
            json={"mode": "online", "state": "waiting", "restricted_to": {}},
        )
        expected_log_params = (
            job_id,
            0,
            TestEvent.PROVISION_SUCCESS,
        )
        with patch.object(
            agent.client, "post_provision_log"
        ) as mock_post_provision_log:
            agent.process_one_job()
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
        requests_mock.get(
            f"http://127.0.0.1:8000/v2/agents/{self.config['agent_id']}/data",
            json={"mode": "online", "state": "waiting", "restricted_to": {}},
        )
        expected_log_params = (
            job_id,
            1,
            TestEvent.PROVISION_FAIL,
        )
        with patch.object(
            agent.client, "post_provision_log"
        ) as mock_post_provision_log:
            agent.process_one_job()
            mock_post_provision_log.assert_called_with(*expected_log_params)

    def test_provision_error_in_event_detail(self, agent, requests_mock):
        """Tests provision log error messages in event log detail field."""
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
        requests_mock.get(
            f"http://127.0.0.1:8000/v2/agents/{self.config['agent_id']}/data",
            json={"mode": "online", "state": "waiting", "restricted_to": {}},
        )
        status_url = f"http://127.0.0.1:8000/v1/job/{job_id}/events"
        requests_mock.post(status_url, status_code=HTTPStatus.OK)

        provision_exception_info = {
            "provision_exception_info": {
                "exception_name": "MyExceptionName",
                "exception_message": "MyExceptionMessage",
                "exception_cause": "MyExceptionCause",
            }
        }

        with patch("shutil.rmtree"):
            with patch(
                "testflinger_agent.agent.TestflingerJob.run_test_phase"
            ) as mock_run_test_phase:

                def run_test_phase_side_effect(phase, rundir):
                    if phase == "provision":
                        provision_log_path = os.path.join(
                            rundir, "device-connector-error.json"
                        )
                        with open(
                            provision_log_path, "w"
                        ) as provision_log_file:
                            provision_log_file.write(
                                json.dumps(provision_exception_info)
                            )
                            provision_log_file.close()
                        return 99, None, ""
                    else:
                        return 0, None, ""

                mock_run_test_phase.side_effect = run_test_phase_side_effect
                agent.process_one_job()

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
        """Tests provision log error messages for exceptions with no cause."""
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
        requests_mock.get(
            f"http://127.0.0.1:8000/v2/agents/{self.config['agent_id']}/data",
            json={"mode": "online", "state": "waiting", "restricted_to": {}},
        )
        status_url = f"http://127.0.0.1:8000/v1/job/{job_id}/events"
        requests_mock.post(status_url, status_code=HTTPStatus.OK)

        provision_exception_info = {
            "provision_exception_info": {
                "exception_name": "MyExceptionName",
                "exception_message": "MyExceptionMessage",
                "exception_cause": None,
            }
        }

        with patch("shutil.rmtree"):
            with patch(
                "testflinger_agent.agent.TestflingerJob.run_test_phase"
            ) as mock_run_test_phase:

                def run_test_phase_side_effect(phase, rundir):
                    if phase == "provision":
                        provision_log_path = os.path.join(
                            rundir, "device-connector-error.json"
                        )
                        with open(
                            provision_log_path, "w"
                        ) as provision_log_file:
                            provision_log_file.write(
                                json.dumps(provision_exception_info)
                            )
                            provision_log_file.close()
                        return 99, None, ""
                    else:
                        return 0, None, ""

                mock_run_test_phase.side_effect = run_test_phase_side_effect
                agent.process_one_job()

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

    def test_agent_metrics(self, agent, requests_mock):
        """
        Tests that total job, total job failures, and phase duration metrics
        are tracked when running a job.
        """
        self.config["provision_command"] = "/bin/false"
        agent_id = self.config["agent_id"]
        mock_job_data = {
            "job_id": str(uuid.uuid1()),
            "job_queue": "test",
            "provision_data": {"url": "foo"},
        }
        requests_mock.get(
            "http://127.0.0.1:8000/v1/job?queue=test",
            [{"text": json.dumps(mock_job_data)}, {"text": "{}"}],
        )
        requests_mock.get(
            f"http://127.0.0.1:8000/v2/agents/{agent_id}/data",
            json={"mode": "online", "state": "waiting", "restricted_to": {}},
        )
        requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)
        with patch("shutil.rmtree"), patch("pathlib.Path.unlink"):
            agent.process_one_job()

        total_jobs = prometheus_client.REGISTRY.get_sample_value(
            "jobs_total", {"agent_id": agent_id}
        )
        total_provision_failures = prometheus_client.REGISTRY.get_sample_value(
            "failures_total",
            {"agent_id": agent_id, "test_phase": TestPhase.PROVISION},
        )
        provision_duration_count = prometheus_client.REGISTRY.get_sample_value(
            "phase_duration_seconds_count",
            {
                "agent_id": agent_id,
                "test_phase": TestPhase.PROVISION,
                "identifier": self.config["identifier"],
                "release": "",
            },
        )
        assert total_provision_failures == 1
        assert total_jobs == 1
        assert provision_duration_count == 1

    def test_agent_metrics_release_label_after_provision(
        self, agent, requests_mock
    ):
        """
        Tests that after a successful provision the release label is populated
        in the phase_duration_seconds metric from the DUT's os-release.
        """
        self.config["provision_command"] = "/bin/true"
        agent_id = self.config["agent_id"]
        mock_job_data = {
            "job_id": str(uuid.uuid1()),
            "job_queue": "test",
            "provision_data": {"url": "foo"},
        }
        requests_mock.get(
            "http://127.0.0.1:8000/v1/job?queue=test",
            [{"text": json.dumps(mock_job_data)}, {"text": "{}"}],
        )
        requests_mock.get(
            f"http://127.0.0.1:8000/v2/agents/{agent_id}/data",
            json={"mode": "online", "state": "waiting", "restricted_to": {}},
        )
        requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)

        device_info = {
            "device_info": {"device_ip": "10.0.0.1", "agent_name": "test01"}
        }
        with (
            patch("shutil.rmtree"),
            patch("pathlib.Path.unlink"),
            patch(
                "testflinger_agent.job.TestflingerJob.get_device_info",
                return_value=device_info,
            ),
            patch(
                "testflinger_agent.agent.query_dut_release",
                return_value="22.04.5",
            ),
        ):
            agent.process_one_job()

        provision_duration_count = prometheus_client.REGISTRY.get_sample_value(
            "phase_duration_seconds_count",
            {
                "agent_id": agent_id,
                "test_phase": TestPhase.PROVISION,
                "identifier": self.config["identifier"],
                "release": "22.04.5",
            },
        )
        assert provision_duration_count == 1

    def test_agent_recovery_failure_metrics(self, agent, requests_mock):
        """Test recovery failure metrics when provision exits with code 46.

        Expected flow:
        1. Agent starts in ONLINE mode (fixture initializes)
        2. Job runs, provision exits with code 46
        3. Agent detects failure and enters MAINTENANCE mode
        4. Agent POSTs mode=maintenance to server
        5. Server stores it in 'mode' field (informational only)
        6. When determine_next_mode() queries server:
           - No 'commanded_mode', so agent uses current_mode
           - Agent stays in MAINTENANCE (no command to change)
        """
        self.config["provision_command"] = "bash -c 'exit 46'"
        agent_id = self.config["agent_id"]
        job_id = str(uuid.uuid1())
        mock_job_data = {
            "job_id": job_id,
            "job_queue": "test",
            "provision_data": {"url": "foo"},
        }
        requests_mock.get(
            "http://127.0.0.1:8000/v1/job?queue=test", json=mock_job_data
        )

        # Server has no commands for the agent (no commanded_mode).
        # The 'mode' field is just informational (what agent reported).
        # This matches the scenario: agent decides to go into maintenance,
        # posts it, server stores it, but doesn't command anything.
        requests_mock.get(
            f"http://127.0.0.1:8000/v2/agents/{agent_id}/data",
            json={
                "mode": "maintenance",
                "state": "waiting",
                "restricted_to": {},
                # Note: No 'commanded_mode' - agent is not being commanded
            },
        )
        requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)
        with patch("shutil.rmtree"), patch("pathlib.Path.unlink"):
            agent.process_one_job()

        recovery_failures = prometheus_client.REGISTRY.get_sample_value(
            "recovery_failures_total", {"agent_id": agent_id}
        )
        assert recovery_failures == 1

        # Verify agent POSTed mode=maintenance to server
        mode_posts = [
            call.json()
            for call in requests_mock.request_history
            if call.method == "POST"
            and "/v2/agents/" in call.path
            and "mode" in (call.json() or {})
        ]
        assert mode_posts, "Agent should have POSTed mode change"
        assert mode_posts[-1]["mode"] == "maintenance", (
            "Agent should have POSTed mode=maintenance after recovery failure"
        )

        # Verify determine_next_mode() keeps agent in maintenance mode
        # (no server command, so agent stays in its current mode)
        mode, _ = agent.determine_next_mode()
        assert mode == AgentMode.MAINTENANCE, (
            "Agent in maintenance with no command should stay in maintenance"
        )

    def test_missing_agent_state(self, agent, requests_mock, caplog):
        """Test default state for an agent is offline if unable to retrieve."""
        self.config["provision_command"] = "/bin/false"
        mock_job_data = {
            "job_id": str(uuid.uuid1()),
            "job_queue": "test",
            "provision_data": {"url": "foo"},
        }
        requests_mock.get(
            f"{agent.client.server}/v1", status_code=HTTPStatus.OK
        )
        requests_mock.get(
            "http://127.0.0.1:8000/v1/job?queue=test",
            [{"text": json.dumps(mock_job_data)}, {"text": "{}"}],
        )
        requests_mock.get(
            f"http://127.0.0.1:8000/v2/agents/{self.config['agent_id']}/data",
            status_code=HTTPStatus.NOT_FOUND,
        )
        requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)
        # Trigger update_agent_data to log the error when unable to retrieve
        agent.determine_next_mode()
        assert "Failed to retrieve agent data" in caplog.text

    def test_set_agent_mode_without_comment_clears_comment(self, agent):
        """An agent returning online explicitly clears its old comment."""
        with patch.object(agent.client, "post_agent_data") as post_agent_data:
            agent.set_agent_mode(AgentMode.ONLINE)

        post_agent_data.assert_called_once_with(
            {"mode": AgentMode.ONLINE, "comment": ""}
        )

    def test_restart_agent_sets_restart_mode(self, agent):
        """A restart request must not be persisted as an offline transition."""
        with (
            patch.object(agent, "set_agent_mode") as set_agent_mode,
            pytest.raises(SystemExit, match="Restart Requested"),
        ):
            agent.restart_agent("apply update")

        set_agent_mode.assert_called_once_with(
            AgentMode.RESTART, "apply update"
        )

    def test_server_wait_for_connectivity(self, agent, requests_mock, caplog):
        """Test agent waits for server availability before processing jobs."""
        # Mock all GET response for server availability
        requests_mock.get(
            f"{agent.client.server}/v1",
            [
                {"status_code": HTTPStatus.SERVICE_UNAVAILABLE},
                {"status_code": HTTPStatus.SERVICE_UNAVAILABLE},
                {"status_code": HTTPStatus.OK},
            ],
        )

        # Mock server connectivity
        with patch("time.sleep"):
            # Server should be unavailable on first check
            assert not agent.client.is_server_reachable()

            # Wait for connectivity to be restored
            agent.client.wait_for_server_connectivity(interval=1)
            # First attempt is also unsuccessful
            assert "Testflinger server unreachable" in caplog.text


class TestStartupState:
    """Tests for _set_startup_state behavior on agent initialization.

    The rule is:
    - OFFLINE → preserve that state (do not come up online)
    - Everything else (MAINTENANCE, RESTART, WAITING, UNKNOWN, any stale
    job-phase state, no state key, empty response, HTTP error / unknown
    agent) → WAITING
    """

    AGENT_ID = "test01"
    SERVER = "127.0.0.1:8000"
    AGENT_DATA_URL = f"http://{SERVER}/v2/agents/{AGENT_ID}/data"

    @pytest.fixture(autouse=True)
    def clear_registry(self):
        collectors = tuple(
            prometheus_client.REGISTRY._collector_to_names.keys()
        )
        for collector in collectors:
            prometheus_client.REGISTRY.unregister(collector)
        yield

    @pytest.fixture
    def base_config(self, tmp_path):
        return validate(
            {
                "agent_id": self.AGENT_ID,
                "polling_interval": 2,
                "server_address": self.SERVER,
                "job_queues": ["test"],
                "execution_basedir": str(tmp_path / "execution"),
                "logging_basedir": str(tmp_path / "logs"),
                "results_basedir": str(tmp_path / "results"),
            }
        )

    def _startup_state_posted(self, requests_mock) -> dict:
        """Return the final state-bearing POST body on startup."""
        state_posts = [
            call.json()
            for call in requests_mock.request_history
            if call.method == "POST"
            and "/v2/agents/" in call.path
            and "state" in (call.json() or {})
        ]
        assert state_posts, (
            "No state POST found — agent never reported a state"
        )
        return state_posts[-1]

    @pytest.fixture(autouse=True)
    def mock_http(self, requests_mock):
        """Register catch-alls first so specific URL mocks take priority."""
        requests_mock.get(rmock.ANY)
        requests_mock.post(rmock.ANY)

    def _make_agent(self, requests_mock, base_config):
        """Instantiate the agent; mock infrastructure is already registered."""
        return _TestflingerAgent(_TestflingerClient(base_config))

    # ------------------------------------------------------------------
    # States that must be PRESERVED (agent stays non-online)
    # ------------------------------------------------------------------

    def test_startup_preserves_offline(self, requests_mock, base_config):
        """Agent respects commanded_mode=OFFLINE on startup and posts it.

        When the server has commanded_mode='offline', the agent must:
        1. Read the commanded_mode from GET
        2. Transition to OFFLINE mode
        3. POST mode='offline' back to server

        The server will then clear the commanded_mode (goal achieved).
        This is safe because there's no race condition: the POST clearing
        the commanded_mode is the proof the agent executed the command.
        """
        requests_mock.get(
            self.AGENT_DATA_URL,
            json={
                "commanded_mode": {
                    "value": "offline",
                    "changed_at": "2026-10-18T00:00:00",
                    "changed_by": "testflinger@example.com",
                    "comment": "set by admin",
                },
            },
        )
        requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)
        self._make_agent(requests_mock, base_config)

        # Verify agent POSTed mode=offline on startup
        mode_posts = [
            call.json()
            for call in requests_mock.request_history
            if call.method == "POST"
            and "/v2/agents/" in call.path
            and "mode" in (call.json() or {})
        ]
        assert mode_posts, "Agent must POST mode on startup"
        # The last mode POST should be offline
        assert mode_posts[-1]["mode"] == "offline", (
            "Agent must POST mode='offline' when commanded_mode='offline'"
        )

    def test_startup_commanded_restart_exits_agent(
        self, requests_mock, base_config
    ):
        """When server commands RESTART, agent POSTs mode=RESTART and exits.

        This tests the initial phase of the RESTART contract:
        1. Server sends commanded_mode=RESTART
        2. Agent reads it and posts mode=RESTART
        3. Agent exits (will be restarted by supervisor)

        On next startup, agent will read mode=RESTART plus a new
        commanded_mode (e.g., ONLINE) set by server, and obey that.
        """
        requests_mock.get(
            self.AGENT_DATA_URL,
            json={
                "commanded_mode": {
                    "value": "restart",
                    "changed_at": "2026-10-18T00:00:00",
                    "changed_by": "testflinger@example.com",
                    "comment": "admin restart",
                },
            },
        )
        requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)

        with pytest.raises(SystemExit, match="Restart Requested"):
            self._make_agent(requests_mock, base_config)

        # Verify agent POSTed mode=restart before exiting
        mode_posts = [
            call.json()
            for call in requests_mock.request_history
            if call.method == "POST"
            and "/v2/agents/" in call.path
            and "mode" in (call.json() or {})
        ]
        assert mode_posts, "Agent must POST mode on startup"
        assert mode_posts[-1]["mode"] == "restart", (
            "Agent must POST mode='restart' when commanded_mode='restart'"
        )

    def test_startup_after_restart_obeys_commanded_mode(
        self, requests_mock, base_config
    ):
        """After RESTART, agent reads new commanded_mode and obeys it.

        This tests the second phase of the RESTART contract:
        1. Agent was last in mode=RESTART (from previous restart command)
        2. Server has set commanded_mode=ONLINE (or OFFLINE, MAINTENANCE, etc.)
        3. Agent reads both mode=RESTART and commanded_mode=ONLINE
        4. Agent obeys commanded_mode=ONLINE (priority over mode=RESTART)
        5. Agent POSTs mode=ONLINE, and server clears commanded_mode

        This scenario handles the case where admin changes their intent
        during the agent's restart window.
        """
        requests_mock.get(
            self.AGENT_DATA_URL,
            json={
                "mode": "restart",
                "commanded_mode": {
                    "value": "online",
                    "changed_at": "2026-10-18T00:00:00",
                    "changed_by": "testflinger@example.com",
                    "comment": "admin changed their mind",
                },
            },
        )
        requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)
        self._make_agent(requests_mock, base_config)

        # Verify agent came up online (WAITING state)
        assert self._startup_state_posted(requests_mock)["state"] == (
            AgentState.WAITING
        )

        # Verify agent POSTed mode=online (not mode=restart)
        mode_posts = [
            call.json()
            for call in requests_mock.request_history
            if call.method == "POST"
            and "/v2/agents/" in call.path
            and "mode" in (call.json() or {})
        ]
        assert mode_posts, "Agent must POST mode on startup"
        assert mode_posts[-1]["mode"] == "online", (
            "Agent must POST mode='online' when commanded_mode='online'"
        )

    @pytest.mark.parametrize(
        "target_mode, expected_state",
        [
            ("online", AgentState.WAITING),
            ("offline", AgentState.OFFLINE),
            ("maintenance", AgentState.WAITING),
        ],
    )
    def test_startup_after_restart_with_various_modes(
        self, requests_mock, base_config, target_mode, expected_state
    ):
        """After RESTART, agent can transition to any valid mode.

        Tests that the RESTART→<target_mode> transition works for all modes:
        - ONLINE (normal operation)
        - OFFLINE (take agent offline)
        - MAINTENANCE (enter maintenance mode)
        """
        requests_mock.get(
            self.AGENT_DATA_URL,
            json={
                "mode": "restart",
                "commanded_mode": {
                    "value": target_mode,
                    "changed_at": "2026-10-18T00:00:00",
                    "changed_by": "testflinger@example.com",
                    "comment": "",
                },
                "comment": f"restart to {target_mode}",
            },
        )
        requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)
        self._make_agent(requests_mock, base_config)

        # Verify agent POSTed correct mode
        mode_posts = [
            call.json()
            for call in requests_mock.request_history
            if call.method == "POST"
            and "/v2/agents/" in call.path
            and "mode" in (call.json() or {})
        ]
        assert mode_posts[-1]["mode"] == target_mode, (
            f"Agent must POST mode='{target_mode}' after restart"
        )

        # For ONLINE and MAINTENANCE modes, verify the state is correct
        if target_mode in ("online", "maintenance"):
            startup_posts = self._startup_state_posted(requests_mock)
            assert startup_posts["state"] == expected_state, (
                f"After restart to {target_mode}, agent should be in "
                f"{expected_state}"
            )

    def test_startup_reactive_restart_via_signal(
        self, requests_mock, base_config
    ):
        """Reactive restart: supervisor triggers via SIGUSR1 signal.

        When supervisor sends SIGUSR1 (not from server commanded_mode),
        agent must still POST mode=RESTART so server can queue next mode.
        This tests that both command sources (server vs supervisor) work.
        """
        requests_mock.get(
            self.AGENT_DATA_URL,
            json={"comment": "no restart commanded"},
        )
        requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)

        agent = _TestflingerAgent(_TestflingerClient(base_config))
        agent.needs_restart = True

        with pytest.raises(SystemExit, match="Restart Requested"):
            agent.handle_mode_changes()

        # Verify agent POSTed mode=restart
        mode_posts = [
            call.json()
            for call in requests_mock.request_history
            if call.method == "POST"
            and "/v2/agents/" in call.path
            and "mode" in (call.json() or {})
        ]
        assert mode_posts, "Agent must POST mode on reactive restart"
        assert mode_posts[-1]["mode"] == "restart", (
            "Agent must POST mode='restart' on reactive restart"
        )

    @pytest.mark.parametrize(
        "prev_mode, next_mode",
        [
            ("online", "offline"),
            ("offline", "maintenance"),
            ("maintenance", "online"),
        ],
    )
    def test_startup_after_reactive_restart_with_various_modes(
        self, requests_mock, base_config, prev_mode, next_mode
    ):
        """Reactive restart: agent can transition to any mode after restarting.

        Tests that reactive restart (via supervisor signal) followed by
        server-commanded mode transition works for all mode combinations.
        """
        requests_mock.get(
            self.AGENT_DATA_URL,
            json={
                "mode": prev_mode,
                "commanded_mode": {
                    "value": next_mode,
                    "changed_at": "2026-10-18T00:00:00",
                    "changed_by": "testflinger@example.com",
                    "comment": "",
                },
                "comment": f"reactive restart, then to {next_mode}",
            },
        )
        requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)
        self._make_agent(requests_mock, base_config)

        # Verify agent transitioned to expected mode
        mode_posts = [
            call.json()
            for call in requests_mock.request_history
            if call.method == "POST"
            and "/v2/agents/" in call.path
            and "mode" in (call.json() or {})
        ]
        assert mode_posts[-1]["mode"] == next_mode, (
            f'Agent should end in mode="{next_mode}", got '
            f"{mode_posts[-1]['mode']}"
        )

    # ------------------------------------------------------------------
    # States that must result in WAITING (agent comes up online)
    # ------------------------------------------------------------------

    @pytest.mark.parametrize(
        "server_state",
        [
            # Maintenance lifecycle handling belongs to the maintenance-mode
            # feature, which must preserve it through startup and polling.
            AgentState.MAINTENANCE,
            AgentState.RESTART,  # explicit restart request → come back online
            AgentState.WAITING,  # already waiting (e.g. clean shutdown)
            AgentState.UNKNOWN,  # local-only sentinel, treat as no useful info
            # stale job-phase states left by a crash
            "setup",
            "provision",
            "test",
            "allocate",
            "reserve",
            "cleanup",
        ],
    )
    def test_startup_comes_up_waiting_for_non_preserved_states(
        self, requests_mock, base_config, server_state
    ):
        """Any state that is not OFFLINE or MAINTENANCE must result in the
        agent coming up as WAITING.
        """
        requests_mock.get(
            self.AGENT_DATA_URL,
            json={"state": server_state, "comment": ""},
        )
        self._make_agent(requests_mock, base_config)
        assert self._startup_state_posted(requests_mock)["state"] == (
            AgentState.WAITING
        )

    @pytest.mark.parametrize(
        "mock_kwargs, description",
        [
            ({"json": {}}, "empty body"),
            ({"json": {"comment": "no state key"}}, "no state key"),
            ({"status_code": HTTPStatus.NOT_FOUND}, "404 unknown agent"),
            (
                {"exc": requests.exceptions.ConnectionError("unreachable")},
                "server unreachable",
            ),
        ],
    )
    def test_startup_comes_up_waiting_when_server_gives_no_state(
        self, requests_mock, base_config, mock_kwargs, description
    ):
        """When the server cannot supply a meaningful state (new agent, error,
        empty response), the agent must come up as WAITING.
        """
        requests_mock.get(self.AGENT_DATA_URL, **mock_kwargs)
        self._make_agent(requests_mock, base_config)
        assert self._startup_state_posted(requests_mock)["state"] == (
            AgentState.WAITING
        )

    def test_startup_comes_up_waiting_when_server_response_is_invalid_json(
        self, requests_mock, base_config
    ):
        """An invalid success response has no usable prior state."""
        requests_mock.get(self.AGENT_DATA_URL, text="not JSON")
        self._make_agent(requests_mock, base_config)
        assert self._startup_state_posted(requests_mock)["state"] == (
            AgentState.WAITING
        )
