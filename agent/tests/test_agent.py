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
import tarfile
import uuid
from http import HTTPStatus
from pathlib import Path
from unittest.mock import patch

import prometheus_client
import requests_mock as rmock
from testflinger_common.enums import AgentState, LogType, TestEvent, TestPhase

import testflinger_agent
from testflinger_agent.config import ATTACHMENTS_DIR
from testflinger_agent.errors import TFServerError


@patch("shutil.rmtree")
def test_check_and_run_setup(
    _rmtree, agent, config, server_api, requests_mock
):
    config["setup_command"] = "echo setup1"
    fake_job_data = {"job_id": str(uuid.uuid1()), "job_queue": "test"}
    requests_mock.get(
        f"{server_api}/agents/data/{config['agent_id']}",
        json={"state": AgentState.WAITING, "restricted_to": {}},
    )
    requests_mock.get(
        f"{server_api}/job?queue=test",
        [{"text": json.dumps(fake_job_data)}, {"text": "{}"}],
    )
    requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)
    agent.process_jobs()
    setuplog = open(
        os.path.join(
            config["execution_basedir"],
            fake_job_data.get("job_id"),
            "setup.log",
        )
    ).read()
    assert "setup1" == setuplog.splitlines()[-1].strip()


@patch("shutil.rmtree")
def test_check_and_run_provision(
    _rmtree, agent, config, server_api, requests_mock
):
    config["provision_command"] = "echo provision1"
    fake_job_data = {
        "job_id": str(uuid.uuid1()),
        "job_queue": "test",
        "provision_data": {"url": "foo"},
    }
    requests_mock.get(
        f"{server_api}/agents/data/{config['agent_id']}",
        json={"state": AgentState.WAITING, "restricted_to": {}},
    )
    requests_mock.get(
        f"{server_api}/job?queue=test",
        [{"text": json.dumps(fake_job_data)}, {"text": "{}"}],
    )
    requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)
    agent.process_jobs()
    provisionlog = open(
        os.path.join(
            config["execution_basedir"],
            fake_job_data.get("job_id"),
            "provision.log",
        )
    ).read()
    assert "provision1" == provisionlog.splitlines()[-1].strip()


@patch("shutil.rmtree")
def test_check_and_run_test(_rmtree, agent, config, server_api, requests_mock):
    config["test_command"] = "echo test1"
    fake_job_data = {
        "job_id": str(uuid.uuid1()),
        "job_queue": "test",
        "test_data": {"test_cmds": "foo"},
    }
    requests_mock.get(
        f"{server_api}/agents/data/{config['agent_id']}",
        json={"state": AgentState.WAITING, "restricted_to": {}},
    )
    requests_mock.get(
        f"{server_api}/job?queue=test",
        [{"text": json.dumps(fake_job_data)}, {"text": "{}"}],
    )
    requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)
    agent.process_jobs()
    testlog = open(
        os.path.join(
            config["execution_basedir"],
            fake_job_data.get("job_id"),
            "test.log",
        )
    ).read()
    assert "test1" == testlog.splitlines()[-1].strip()


def test_attachments(agent, config, server_api, tmp_path):
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
            f"{server_api}/agents/data/{config['agent_id']}",
            json={"state": AgentState.WAITING, "restricted_to": {}},
        )

        # request and process the job (should unpack the archive)
        with patch("shutil.rmtree"):
            agent.process_jobs()

        # check the request history to confirm that:
        # - there is a request to the job retrieval endpoint
        # - there a request to the attachment retrieval endpoint
        history = mocker.request_history
        request_paths = [req.path for req in history]
        assert "/v1/job" in request_paths
        assert f"/v1/job/{job_id}/attachments" in request_paths

        # check that the attachment is where it's supposed to be
        basepath = Path(config["execution_basedir"]) / mock_job_data["job_id"]
        attachment = basepath / ATTACHMENTS_DIR / archive_name
        assert attachment.exists()


def test_attachments_insecure_no_phase(agent, config, server_api, tmp_path):
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
            f"{server_api}/agents/data/{config['agent_id']}",
            json={"state": AgentState.WAITING, "restricted_to": {}},
        )

        # request and process the job (should unpack the archive)
        with patch("shutil.rmtree"):
            agent.process_jobs()

        # check the request history to confirm that:
        # - there is a request to the job retrieval endpoint
        # - there a request to the attachment retrieval endpoint
        history = mocker.request_history
        request_paths = [req.path for req in history]
        assert "/v1/job" in request_paths
        assert f"/v1/job/{job_id}/attachments" in request_paths

        # check that the attachment is *not* where it's supposed to be
        basepath = Path(config["execution_basedir"]) / mock_job_data["job_id"]
        attachment = basepath / ATTACHMENTS_DIR / archive_name
        assert not attachment.exists()


def test_attachments_insecure_out_of_hierarchy(
    agent, config, server_api, tmp_path
):
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
            f"{server_api}/agents/data/{config['agent_id']}",
            json={"state": AgentState.WAITING, "restricted_to": {}},
        )

        # request and process the job (should unpack the archive)
        with patch("shutil.rmtree"):
            agent.process_jobs()

        # check the request history to confirm that:
        # - there is a request to the job retrieval endpoint
        # - there a request to the attachment retrieval endpoint
        history = mocker.request_history
        request_paths = [req.path for req in history]
        assert "/v1/job" in request_paths
        assert f"/v1/job/{job_id}/attachments" in request_paths

        # check that the attachment is *not* where it's supposed to be
        basepath = Path(config["execution_basedir"]) / mock_job_data["job_id"]
        attachment = basepath / ATTACHMENTS_DIR / archive_name
        assert not attachment.exists()


@patch("shutil.rmtree")
def test_config_vars_in_env(_rmtree, agent, config, server_api, requests_mock):
    config["test_command"] = "bash -c 'echo agent_id is $agent_id'"
    mock_job_data = {
        "job_id": str(uuid.uuid1()),
        "job_queue": "test",
        "test_data": {"test_cmds": "foo"},
    }
    requests_mock.get(
        f"{server_api}/agents/data/{config['agent_id']}",
        json={"state": AgentState.WAITING, "restricted_to": {}},
    )
    requests_mock.get(
        f"{server_api}/job?queue=test",
        [{"text": json.dumps(mock_job_data)}, {"text": "{}"}],
    )
    requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)
    agent.process_jobs()
    testlog = open(
        os.path.join(
            config["execution_basedir"],
            mock_job_data.get("job_id"),
            "test.log",
        )
    ).read()
    assert config["agent_id"] in testlog


@patch("pathlib.Path.unlink")
@patch("shutil.rmtree")
def test_phase_failed(
    _rmtree, _unlink, agent, config, server_api, requests_mock
):
    # Make sure we stop running after a failed phase
    config["provision_command"] = "/bin/false"
    config["test_command"] = "echo test1"
    mock_job_data = {
        "job_id": str(uuid.uuid1()),
        "job_queue": "test",
        "provision_data": {"url": "foo"},
        "test_data": {"test_cmds": "foo"},
    }
    requests_mock.get(
        f"{server_api}/agents/data/{config['agent_id']}",
        json={"state": AgentState.WAITING, "restricted_to": {}},
    )
    requests_mock.get(
        f"{server_api}/job?queue=test",
        [{"text": json.dumps(mock_job_data)}, {"text": "{}"}],
    )
    requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)
    agent.process_jobs()
    outcome_file = os.path.join(
        os.path.join(
            config["execution_basedir"],
            mock_job_data.get("job_id"),
            "testflinger-outcome.json",
        )
    )
    with open(outcome_file) as f:
        outcome_data = json.load(f)
    assert outcome_data.get("status").get("provision") == 1
    assert outcome_data.get("status").get("test") is None


@patch("pathlib.Path.unlink")
@patch("shutil.rmtree")
def test_phase_timeout(
    _rmtree, _unlink, agent, config, server_api, requests_mock
):
    # Make sure the status code of a timed-out phase is correct
    config["test_command"] = "sleep 12"
    mock_job_data = {
        "job_id": str(uuid.uuid1()),
        "job_queue": "test",
        "output_timeout": 1,
        "test_data": {"test_cmds": "foo"},
    }
    requests_mock.get(
        f"{server_api}/agents/data/{config['agent_id']}",
        json={"state": AgentState.WAITING, "restricted_to": {}},
    )
    requests_mock.get(
        f"{server_api}/job?queue=test",
        [{"text": json.dumps(mock_job_data)}, {"text": "{}"}],
    )
    requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)
    agent.process_jobs()
    outcome_file = os.path.join(
        os.path.join(
            config["execution_basedir"],
            mock_job_data.get("job_id"),
            "testflinger-outcome.json",
        )
    )
    with open(outcome_file) as f:
        outcome_data = json.load(f)
    assert outcome_data.get("status").get("test") == 247


@patch.object(
    testflinger_agent.client.TestflingerClient, "transmit_job_outcome"
)
def test_retry_transmit(
    mock_transmit_job_outcome, agent, config, server_api, requests_mock
):
    # Make sure we retry sending test results
    config["provision_command"] = "/bin/false"
    config["test_command"] = "echo test1"
    mock_job_data = {"job_id": str(uuid.uuid1()), "job_queue": "test"}
    # Send an extra empty data since we will be calling get 3 times
    requests_mock.get(
        f"{server_api}/job?queue=test",
        [
            {"text": json.dumps(mock_job_data)},
            {"text": "{}"},
            {"text": "{}"},
        ],
    )
    requests_mock.get(
        f"{server_api}/agents/data/{config['agent_id']}",
        json={"state": AgentState.WAITING, "restricted_to": {}},
    )
    requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)
    # Make sure we fail the first time when transmitting the results
    mock_transmit_job_outcome.side_effect = [TFServerError(404), ""]
    agent.process_jobs()
    first_dir = os.path.join(
        config["execution_basedir"],
        mock_job_data.get("job_id"),
    )
    mock_transmit_job_outcome.assert_called_with(first_dir)
    # Try processing jobs again, now it should be in results_basedir
    agent.process_jobs()
    retry_dir = os.path.join(
        config["results_basedir"], mock_job_data.get("job_id")
    )
    mock_transmit_job_outcome.assert_called_with(retry_dir)


def test_recovery_failed(agent, config, server_api, requests_mock):
    # Make sure we stop processing jobs after a device recovery error
    config["provision_command"] = "bash -c 'exit 46'"
    config["test_command"] = "echo test1"
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
        m.get(f"{agent.client.server}/v1", status_code=HTTPStatus.OK)
        m.get(f"{server_api}/job?queue=test", json=fake_job_data)
        m.get(f"{server_api}/result/{job_id}", text="{}")
        m.post(f"{server_api}/result/{job_id}", text="{}")
        m.post(
            f"{server_api}/result/{job_id}/log/{LogType.STANDARD_OUTPUT}",
            text="{}",
        )
        m.post(
            f"{server_api}/agents/data/{config.get('agent_id')}",
            text="OK",
        )
        m.get(
            f"{server_api}/agents/data/{config.get('agent_id')}",
            [
                {
                    "text": json.dumps(
                        {"state": AgentState.WAITING, "restricted_to": {}}
                    )
                },
                {
                    "text": json.dumps(
                        {"state": AgentState.OFFLINE, "restricted_to": {}}
                    )
                },
            ],
        )

        agent.process_jobs()
        assert agent.check_offline()


@patch.object(testflinger_agent.client.TestflingerClient, "post_agent_data")
def test_post_agent_data(mock_post_agent_data, agent, config):
    # Make sure we post the initial agent data
    agent._post_initial_agent_data()
    mock_post_agent_data.assert_called_with(
        {
            "identifier": config["identifier"],
            "queues": config["job_queues"],
            "location": config["location"],
            "provision_type": config["provision_type"],
        }
    )


@patch("shutil.rmtree")
def test_post_agent_status_update(
    _rmtree, agent, config, server_api, requests_mock
):
    config["test_command"] = "echo test1"
    job_id = str(uuid.uuid1())
    fake_job_data = {
        "job_id": job_id,
        "job_queue": "test",
        "test_data": {"test_cmds": "foo"},
        "job_status_webhook": "https://mywebhook",
    }
    requests_mock.get(
        f"{server_api}/job?queue=test",
        [{"text": json.dumps(fake_job_data)}, {"text": "{}"}],
    )
    requests_mock.get(
        f"{server_api}/agents/data/{config['agent_id']}",
        json={"state": AgentState.WAITING, "restricted_to": {}},
    )
    status_url = f"{server_api}/job/{job_id}/events"
    requests_mock.post(status_url, status_code=HTTPStatus.OK)
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
        for phase in TestPhase
        for postfix in ["_start", "_success"]
    ]
    expected_event_name_list.insert(0, "job_start")
    expected_event_name_list.append("job_end")

    assert event_list[-1]["detail"] == "normal_exit"
    assert event_name_list == expected_event_name_list


@patch("shutil.rmtree")
def test_post_agent_status_update_cancelled(
    _rmtree, agent, config, server_api, requests_mock
):
    config["test_command"] = "echo test1"
    job_id = str(uuid.uuid1())
    fake_job_data = {
        "job_id": job_id,
        "job_queue": "test",
        "test_data": {"test_cmds": "foo"},
        "job_status_webhook": "https://mywebhook",
    }
    requests_mock.get(
        f"{server_api}/job?queue=test",
        [{"text": json.dumps(fake_job_data)}, {"text": "{}"}],
    )
    requests_mock.get(
        f"{server_api}/agents/data/{config['agent_id']}",
        json={"state": AgentState.WAITING, "restricted_to": {}},
    )
    status_url = f"{server_api}/job/{job_id}/events"
    requests_mock.post(status_url, status_code=HTTPStatus.OK)

    requests_mock.get(
        f"{server_api}/result/{job_id}",
        json={"job_state": "cancelled"},
    )
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


@patch("shutil.rmtree")
def test_post_agent_status_update_global_timeout(
    _rmtree, agent, config, server_api, requests_mock
):
    config["test_command"] = "sleep 12"
    job_id = str(uuid.uuid1())
    fake_job_data = {
        "job_id": job_id,
        "job_queue": "test",
        "test_data": {"test_cmds": "foo"},
        "job_status_webhook": "https://mywebhook",
        "global_timeout": 1,
    }
    requests_mock.get(
        f"{server_api}/job?queue=test",
        [{"text": json.dumps(fake_job_data)}, {"text": "{}"}],
    )
    requests_mock.get(
        f"{server_api}/agents/data/{config['agent_id']}",
        json={"state": AgentState.WAITING, "restricted_to": {}},
    )
    status_url = f"{server_api}/job/{job_id}/events"
    requests_mock.post(status_url, status_code=HTTPStatus.OK)

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


@patch("shutil.rmtree")
def test_post_agent_status_update_output_timeout(
    _rmtree, agent, config, server_api, requests_mock
):
    config["test_command"] = "sleep 12"
    job_id = str(uuid.uuid1())
    fake_job_data = {
        "job_id": job_id,
        "job_queue": "test",
        "test_data": {"test_cmds": "foo"},
        "job_status_webhook": "https://mywebhook",
        "output_timeout": 1,
    }
    requests_mock.get(
        f"{server_api}/job?queue=test",
        [{"text": json.dumps(fake_job_data)}, {"text": "{}"}],
    )
    requests_mock.get(
        f"{server_api}/agents/data/{config['agent_id']}",
        json={"state": AgentState.WAITING, "restricted_to": {}},
    )
    status_url = f"{server_api}/job/{job_id}/events"
    requests_mock.post(status_url, status_code=HTTPStatus.OK)

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


def test_post_provision_log_success(agent, config, server_api, requests_mock):
    # Ensure provision log is posted when the provision phase succeeds
    config["provision_command"] = "echo provision1"
    job_id = str(uuid.uuid1())
    fake_job_data = {
        "job_id": job_id,
        "job_queue": "test",
        "provision_data": {"url": "foo"},
    }
    requests_mock.get(
        f"{server_api}/job?queue=test",
        [{"text": json.dumps(fake_job_data)}, {"text": "{}"}],
    )
    requests_mock.get(
        f"{server_api}/agents/data/{config['agent_id']}",
        json={"state": AgentState.WAITING, "restricted_to": {}},
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


def test_post_provision_log_fail(agent, config, server_api, requests_mock):
    # Ensure provision log is posted when the provision phase fails
    config["provision_command"] = "exit 1"
    job_id = str(uuid.uuid1())
    fake_job_data = {
        "job_id": job_id,
        "job_queue": "test",
        "provision_data": {"url": "foo"},
    }
    requests_mock.get(
        f"{server_api}/job?queue=test",
        [{"text": json.dumps(fake_job_data)}, {"text": "{}"}],
    )
    requests_mock.get(
        f"{server_api}/agents/data/{config['agent_id']}",
        json={"state": AgentState.WAITING, "restricted_to": {}},
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


@patch("testflinger_agent.agent.TestflingerJob.run_test_phase")
@patch("shutil.rmtree")
def test_provision_error_in_event_detail(
    _rmtree, mock_run_test_phase, agent, config, server_api, requests_mock
):
    """Tests provision log error messages in event log detail field."""
    config["test_command"] = "echo test1"
    job_id = str(uuid.uuid1())
    fake_job_data = {
        "job_id": job_id,
        "job_queue": "test",
        "test_data": {"test_cmds": "foo"},
        "job_status_webhook": "https://mywebhook",
    }
    requests_mock.get(
        f"{server_api}/job?queue=test",
        [{"text": json.dumps(fake_job_data)}, {"text": "{}"}],
    )
    requests_mock.get(
        f"{server_api}/agents/data/{config['agent_id']}",
        json={"state": AgentState.WAITING, "restricted_to": {}},
    )
    status_url = f"{server_api}/job/{job_id}/events"
    requests_mock.post(status_url, status_code=HTTPStatus.OK)

    provision_exception_info = {
        "provision_exception_info": {
            "exception_name": "MyExceptionName",
            "exception_message": "MyExceptionMessage",
            "exception_cause": "MyExceptionCause",
        }
    }

    def run_test_phase_side_effect(phase, rundir):
        if phase == "provision":
            provision_log_path = os.path.join(
                rundir, "device-connector-error.json"
            )
            with open(provision_log_path, "w") as provision_log_file:
                provision_log_file.write(json.dumps(provision_exception_info))
                provision_log_file.close()
            return 99, None, ""
        else:
            return 0, None, ""

    mock_run_test_phase.side_effect = run_test_phase_side_effect
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


@patch("testflinger_agent.agent.TestflingerJob.run_test_phase")
@patch("shutil.rmtree")
def test_provision_error_no_cause(
    _rmtree, mock_run_test_phase, agent, config, server_api, requests_mock
):
    """Tests provision log error messages for exceptions with no cause."""
    config["test_command"] = "echo test1"
    job_id = str(uuid.uuid1())
    fake_job_data = {
        "job_id": job_id,
        "job_queue": "test",
        "test_data": {"test_cmds": "foo"},
        "job_status_webhook": "https://mywebhook",
    }
    requests_mock.get(
        f"{server_api}/job?queue=test",
        [{"text": json.dumps(fake_job_data)}, {"text": "{}"}],
    )
    requests_mock.get(
        f"{server_api}/agents/data/{config['agent_id']}",
        json={"state": AgentState.WAITING, "restricted_to": {}},
    )
    status_url = f"{server_api}/job/{job_id}/events"
    requests_mock.post(status_url, status_code=HTTPStatus.OK)

    provision_exception_info = {
        "provision_exception_info": {
            "exception_name": "MyExceptionName",
            "exception_message": "MyExceptionMessage",
            "exception_cause": None,
        }
    }

    def run_test_phase_side_effect(phase, rundir):
        if phase == "provision":
            provision_log_path = os.path.join(
                rundir, "device-connector-error.json"
            )
            with open(provision_log_path, "w") as provision_log_file:
                provision_log_file.write(json.dumps(provision_exception_info))
                provision_log_file.close()
            return 99, None, ""
        else:
            return 0, None, ""

    mock_run_test_phase.side_effect = run_test_phase_side_effect
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
    assert provision_fail_event_detail == "MyExceptionName: MyExceptionMessage"


@patch("pathlib.Path.unlink")
@patch("shutil.rmtree")
def test_agent_metrics(
    _rmtree, _unlink, agent, config, server_api, requests_mock
):
    """
    Tests that total job, total job failures, and phase duration metrics
    are tracked when running a job.
    """
    config["provision_command"] = "/bin/false"
    agent_id = config["agent_id"]
    mock_job_data = {
        "job_id": str(uuid.uuid1()),
        "job_queue": "test",
        "provision_data": {"url": "foo"},
    }
    requests_mock.get(
        f"{server_api}/job?queue=test",
        [{"text": json.dumps(mock_job_data)}, {"text": "{}"}],
    )
    requests_mock.get(
        f"{server_api}/agents/data/{agent_id}",
        json={"state": AgentState.WAITING, "restricted_to": {}},
    )
    requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)
    agent.process_jobs()

    total_jobs = prometheus_client.REGISTRY.get_sample_value(
        "jobs_total", {"agent_id": agent_id}
    )
    total_provision_failures = prometheus_client.REGISTRY.get_sample_value(
        "failures_total",
        {"agent_id": agent_id, "test_phase": TestPhase.PROVISION},
    )
    provision_duration_count = prometheus_client.REGISTRY.get_sample_value(
        "phase_duration_seconds_count",
        {"agent_id": agent_id, "test_phase": TestPhase.PROVISION},
    )
    assert total_provision_failures == 1
    assert total_jobs == 1
    assert provision_duration_count == 1


@patch("pathlib.Path.unlink")
@patch("shutil.rmtree")
def test_agent_recovery_failure_metrics(
    _rmtree, _unlink, agent, config, server_api, requests_mock
):
    """
    Tests that recovery failure metrics are tracked when a phase
    exits with code 46.
    """
    config["provision_command"] = "bash -c 'exit 46'"
    agent_id = config["agent_id"]
    job_id = str(uuid.uuid1())
    mock_job_data = {
        "job_id": job_id,
        "job_queue": "test",
        "provision_data": {"url": "foo"},
    }
    requests_mock.get(f"{server_api}/job?queue=test", json=mock_job_data)
    requests_mock.get(
        f"{server_api}/agents/data/{agent_id}",
        [
            {
                "text": json.dumps(
                    {"state": AgentState.WAITING, "restricted_to": {}}
                )
            },
            {
                "text": json.dumps(
                    {"state": AgentState.OFFLINE, "restricted_to": {}}
                )
            },
        ],
    )
    requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)
    agent.process_jobs()

    recovery_failures = prometheus_client.REGISTRY.get_sample_value(
        "recovery_failures_total", {"agent_id": agent_id}
    )
    assert recovery_failures == 1
    assert agent.check_offline()


@patch("shutil.rmtree")
def test_missing_agent_state(
    _rmtree, agent, config, server_api, requests_mock, caplog
):
    """Test default state for an agent is offline if unable to retrieve."""
    config["provision_command"] = "/bin/false"
    mock_job_data = {
        "job_id": str(uuid.uuid1()),
        "job_queue": "test",
        "provision_data": {"url": "foo"},
    }
    requests_mock.get(f"{agent.client.server}/v1", status_code=HTTPStatus.OK)
    requests_mock.get(
        f"{server_api}/job?queue=test",
        [{"text": json.dumps(mock_job_data)}, {"text": "{}"}],
    )
    requests_mock.get(
        f"{server_api}/agents/data/{config['agent_id']}",
        status_code=HTTPStatus.NOT_FOUND,
    )
    requests_mock.post(rmock.ANY, status_code=HTTPStatus.OK)
    agent.process_jobs()
    assert "Failed to retrieve agent data" in caplog.text


@patch("time.sleep")
def test_server_wait_for_connectivity(_sleep, agent, requests_mock, caplog):
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

    # Server should be unavailable on first check
    assert not agent.client.is_server_reachable()

    # Wait for connectivity to be restored
    agent.client.wait_for_server_connectivity(interval=1)
    # First attempt is also unsuccessful
    assert "Testflinger server unreachable" in caplog.text


def test_get_job_data_success(agent):
    """Test get_job_data returns job when successful."""
    fake_job = {"job_id": "123", "job_queue": "test"}
    with patch.object(agent.client, "check_jobs", return_value=fake_job):
        result = agent.get_job_data()
    assert result == fake_job


def test_get_job_data_returns_none(agent):
    """When check_jobs returns None, get_job_data returns None."""
    with patch.object(
        agent.client,
        "check_jobs",
        return_value=None,
    ):
        result = agent.get_job_data()

    # Verify None is returned when check_jobs returns None
    assert result is None
