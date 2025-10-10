# Copyright (C) 2022 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

"""Unit tests for testflinger-cli."""

import io
import json
import os
import re
import sys
import tarfile
import uuid
from http import HTTPStatus
from pathlib import Path

import pytest
import requests
import requests_mock as rmock
from requests_mock import Mocker

import testflinger_cli
from testflinger_cli.client import HTTPError
from testflinger_cli.errors import NetworkError

URL = "https://testflinger.canonical.com"


def test_status(capsys, requests_mock):
    """Status should report job_state data."""
    jobid = str(uuid.uuid1())
    fake_return = {"job_state": "completed"}
    requests_mock.get(URL + "/v1/result/" + jobid, json=fake_return)
    sys.argv = ["", "status", jobid]
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.status()
    std = capsys.readouterr()
    assert std.out == "completed\n"


def test_cancel_503(requests_mock):
    """Cancel should fail loudly if cancel action returns 503."""
    jobid = str(uuid.uuid1())
    requests_mock.post(
        URL + "/v1/job/" + jobid + "/action",
        status_code=503,
    )
    sys.argv = ["", "cancel", jobid]
    tfcli = testflinger_cli.TestflingerCli()
    with pytest.raises(HTTPError) as err:
        tfcli.cancel()
    assert err.value.status == 503


def test_cancel(requests_mock):
    """Cancel should fail if /v1/job/<job_id>/action URL returns 400 code."""
    jobid = str(uuid.uuid1())
    requests_mock.post(
        URL + "/v1/job/" + jobid + "/action",
        status_code=400,
    )
    sys.argv = ["", "cancel", jobid]
    tfcli = testflinger_cli.TestflingerCli()
    with pytest.raises(SystemExit) as err:
        tfcli.cancel()
    assert "already completed/cancelled" in err.value.args[0]


def test_submit(capsys, tmp_path, requests_mock):
    """Make sure jobid is read back from submitted job."""
    jobid = str(uuid.uuid1())
    fake_data = {"job_queue": "fake", "provision_data": {"distro": "fake"}}
    testfile = tmp_path / "test.json"
    testfile.write_text(json.dumps(fake_data))
    fake_return = {"job_id": jobid}
    requests_mock.post(URL + "/v1/job", json=fake_return)
    requests_mock.get(
        URL + "/v1/queues/fake/agents",
        json=[{"name": "fake_agent", "state": "waiting"}],
    )
    sys.argv = ["", "submit", str(testfile)]
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.submit()
    std = capsys.readouterr()
    assert jobid in std.out


def test_submit_stdin(capsys, monkeypatch, requests_mock):
    """Make sure jobid is read back from submitted job via stdin."""
    jobid = str(uuid.uuid1())
    fake_data = {"job_queue": "fake", "provision_data": {"distro": "fake"}}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(fake_data)))
    fake_return = {"job_id": jobid}
    requests_mock.post(URL + "/v1/job", json=fake_return)
    requests_mock.get(
        URL + "/v1/queues/fake/agents",
        json=[{"name": "fake_agent", "state": "waiting"}],
    )
    sys.argv = ["", "submit", "-"]
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.submit()
    std = capsys.readouterr()
    assert jobid in std.out


def test_submit_bad_data(tmp_path, requests_mock):
    """Ensure a 422 response from bad data shows the returned errors."""
    fake_data = {"badkey": "badvalue", "job_queue": "fake"}
    testfile = tmp_path / "test.json"
    testfile.write_text(json.dumps(fake_data))
    # return 422 and "expected error"
    requests_mock.post(URL + "/v1/job", status_code=422, text="expected error")
    requests_mock.get(
        URL + "/v1/queues/fake/agents",
        json=[{"name": "fake_agent", "state": "waiting"}],
    )
    sys.argv = ["", "submit", str(testfile)]
    tfcli = testflinger_cli.TestflingerCli()
    with pytest.raises(SystemExit) as err:
        tfcli.submit()
    assert (
        "Unexpected error status from testflinger server: [422] expected error"
        in err.value.code
    )


def test_pack_attachments(tmp_path):
    """Make sure attachments are packed correctly."""
    attachments = [
        Path() / "file_0.bin",
        Path() / "folder" / "file_1.bin",
    ]
    attachment_path = tmp_path / "attachments"

    # create attachment files in the attachment path
    for file in attachments:
        attachment = attachment_path / file
        attachment.parent.mkdir(parents=True)
        attachment.write_bytes(os.urandom(128))

    attachment_data = {
        "test": [
            {
                # relative local file path
                "local": str(attachments[0])
            },
            {
                # relative local file path in folder
                "local": str(attachments[1])
            },
            {
                # absolute local file path, agent path in folder
                "local": str((attachment_path / attachments[0]).resolve()),
                "agent": "folder/file_2.bin",
            },
            {
                # relative local path is a directory
                "local": str(attachments[1].parent),
                "agent": "folder/deeper/",
            },
            {
                # agent path is absolute (stripped, becomes relative)
                "local": str(attachments[0]),
                "agent": "/file_3.bin",
            },
        ]
    }

    # the job.yaml is also in the attachments path
    # (and relative attachment paths are interpreted in relation to that)
    sys.argv = ["", "submit", f"{attachment_path}/job.yaml"]
    tfcli = testflinger_cli.TestflingerCli()
    archive = tmp_path / "attachments.tar.gz"
    tfcli.pack_attachments(archive, attachment_data)

    with tarfile.open(archive) as archive:
        filenames = archive.getnames()
        print(filenames)
        assert "test/file_0.bin" in filenames
        assert "test/folder/file_1.bin" in filenames
        assert "test/folder/file_2.bin" in filenames
        assert "test/folder/deeper/file_1.bin" in filenames
        assert "test/file_3.bin" in filenames


def test_pack_attachments_with_reference(tmp_path):
    """Make sure attachments are packed correctly when using a reference."""
    attachments = [
        Path() / "file_0.bin",
        Path() / "folder" / "file_1.bin",
    ]
    attachment_path = tmp_path / "attachments"

    # create attachment files
    for file in attachments:
        attachment = attachment_path / file
        attachment.parent.mkdir(parents=True)
        attachment.write_bytes(os.urandom(128))

    attachment_data = {
        "test": [
            {
                # relative local file path
                "local": str(attachments[0])
            },
            {
                # relative local file path in folder
                "local": str(attachments[1])
            },
            {
                # absolute local file path, agent path in folder
                "local": str((attachment_path / attachments[0]).resolve()),
                "agent": "folder/file_2.bin",
            },
            {
                # relative local path is a directory
                "local": str(attachments[1].parent),
                "agent": "folder/deeper/",
            },
            {
                # agent path is absolute (stripped, becomes relative)
                "local": str(attachments[0]),
                "agent": "/file_3.bin",
            },
        ]
    }

    # the job.yaml is in the tmp_path
    # (so packing the attachments with fail without specifying that
    # attachments are relative to the attachments path)
    sys.argv = ["", "submit", f"{tmp_path}/job.yaml"]
    tfcli = testflinger_cli.TestflingerCli()
    archive = tmp_path / "attachments.tar.gz"
    with pytest.raises(FileNotFoundError):
        # this fails because the job file is in `tmp_path` whereas
        # attachments are in `tmp_path/attachments`
        tfcli.pack_attachments(archive, attachment_data)

    # the job.yaml is in the tmp_path
    # (but now attachments are relative to the attachments path)
    sys.argv = [
        "",
        "submit",
        f"{tmp_path}/job.yaml",
        "--attachments-relative-to",
        f"{attachment_path}",
    ]
    tfcli = testflinger_cli.TestflingerCli()
    archive = tmp_path / "attachments.tar.gz"
    tfcli.pack_attachments(archive, attachment_data)

    with tarfile.open(archive) as archive:
        filenames = archive.getnames()
        print(filenames)
        assert "test/file_0.bin" in filenames
        assert "test/folder/file_1.bin" in filenames
        assert "test/folder/file_2.bin" in filenames
        assert "test/folder/deeper/file_1.bin" in filenames
        assert "test/file_3.bin" in filenames


def test_submit_with_attachments(tmp_path):
    """Make sure jobs with attachments are submitted correctly."""
    job_id = str(uuid.uuid1())
    job_file = tmp_path / "test.json"
    job_data = {
        "job_queue": "fake",
        "test_data": {
            "attachments": [
                {
                    # include the submission JSON itself as a test attachment
                    "local": str(job_file)
                }
            ]
        },
    }
    job_file.write_text(json.dumps(job_data))

    sys.argv = ["", "submit", str(job_file)]
    tfcli = testflinger_cli.TestflingerCli()

    with Mocker() as mocker:
        # register responses for job and attachment submission endpoints
        mock_response = {"job_id": job_id}
        mocker.post(f"{URL}/v1/job", json=mock_response)
        mocker.post(f"{URL}/v1/job/{job_id}/attachments")
        mocker.get(
            f"{URL}/v1/queues/fake/agents",
            json=[{"name": "fake_agent", "state": "waiting"}],
        )

        # use cli to submit the job (processes `sys.argv` for arguments)
        tfcli.submit()

        # check the request history to confirm that:
        # - there is a request to the job submission endpoint
        # - there a request to the attachment submission endpoint
        history = mocker.request_history
        assert len(history) == 3
        assert history[1].path == "/v1/job"
        assert history[2].path == f"/v1/job/{job_id}/attachments"

        # extract the binary file data from the request
        # (`requests_mock` only provides access to the `PreparedRequest`)
        match = re.search(b"\r\n\r\n(.+)\r\n--", history[-1].body, re.DOTALL)
        data = match.group(1)
        # write the binary data to a file
        with open("attachments.tar.gz", "wb") as attachments:
            attachments.write(data)
        # and check that the contents match the originals
        with tarfile.open("attachments.tar.gz") as attachments:
            filenames = attachments.getnames()
            assert len(filenames) == 1
            attachments.extract(filenames[0], filter="data")
        with open(filenames[0], "r", encoding="utf-8") as attachment:
            assert json.load(attachment) == job_data


def test_submit_attachments_retries(tmp_path):
    """Check retries after unsuccessful attachment submissions."""
    job_id = str(uuid.uuid1())
    job_file = tmp_path / "test.json"
    job_data = {
        "job_queue": "fake",
        "test_data": {
            "attachments": [
                {
                    # include the submission JSON itself as a test attachment
                    "local": str(job_file)
                }
            ]
        },
    }
    job_file.write_text(json.dumps(job_data))

    sys.argv = ["", "submit", str(job_file)]
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.config.data["attachments_retry_wait"] = 1
    tfcli.config.data["attachments_timeout"] = 2
    tfcli.config.data["attachments_tries"] = 4

    with Mocker() as mocker:
        # register responses for job and attachment submission endpoints
        mock_response = {"job_id": job_id}
        mocker.post(f"{URL}/v1/job", json=mock_response)
        mocker.post(
            f"{URL}/v1/job/{job_id}/attachments",
            [
                {"exc": requests.exceptions.ConnectionError},
                {"exc": requests.exceptions.ConnectTimeout},
                {"exc": requests.exceptions.ReadTimeout},
                {"status_code": 200},
            ],
        )
        mocker.get(
            f"{URL}/v1/queues/fake/agents",
            json=[{"name": "fake_agent", "state": "waiting"}],
        )

        # use cli to submit the job (processes `sys.argv` for arguments)
        tfcli.submit()

        # check the request history to confirm that:
        # - there is a request to the job submission endpoint
        # - there are repeated requests to the attachment submission endpoint
        history = mocker.request_history
        assert len(history) == 6
        assert history[1].path == "/v1/job"
        for entry in history[2:]:
            assert entry.path == f"/v1/job/{job_id}/attachments"


def test_submit_attachments_no_retries(tmp_path):
    """Check no retries after attachment submission fails unrecoverably."""
    job_id = str(uuid.uuid1())
    job_file = tmp_path / "test.json"
    job_data = {
        "job_queue": "fake",
        "test_data": {
            "attachments": [
                {
                    # include the submission JSON itself as a test attachment
                    "local": str(job_file)
                }
            ]
        },
    }
    job_file.write_text(json.dumps(job_data))

    sys.argv = ["", "submit", str(job_file)]
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.config.data["attachments_tries"] = 2

    with Mocker() as mocker:
        # register responses for job and attachment submission endpoints
        mocker.post(f"{URL}/v1/job", json={"job_id": job_id})
        mocker.post(
            f"{URL}/v1/job/{job_id}/attachments", [{"status_code": 400}]
        )
        mocker.post(f"{URL}/v1/job/{job_id}/action", [{"status_code": 200}])
        mocker.get(
            f"{URL}/v1/queues/fake/agents",
            json=[{"name": "fake_agent", "state": "waiting"}],
        )

        with pytest.raises(SystemExit) as exc_info:
            # use cli to submit the job (processes `sys.argv` for arguments)
            tfcli.submit()
            assert "failed to submit attachments" in exc_info.value

        # check the request history to confirm that:
        # - there is a request to the job submission endpoint
        # - there is a single request to the attachment submission endpoint:
        #   no retries
        # - there is a final request to cancel the action
        history = mocker.request_history
        assert len(history) == 4
        assert history[1].path == "/v1/job"
        assert history[2].path == f"/v1/job/{job_id}/attachments"
        assert history[3].path == f"/v1/job/{job_id}/action"


def test_submit_attachments_timeout(tmp_path):
    """Make timeout after repeated attachment submission timeouts."""
    job_id = str(uuid.uuid1())
    job_file = tmp_path / "test.json"
    job_data = {
        "job_queue": "fake",
        "test_data": {
            "attachments": [
                {
                    # include the submission JSON itself as a test attachment
                    "local": str(job_file)
                }
            ]
        },
    }
    job_file.write_text(json.dumps(job_data))

    sys.argv = ["", "submit", str(job_file)]
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.config.data["attachments_retry_wait"] = 1
    tfcli.config.data["attachments_timeout"] = 2
    tfcli.config.data["attachments_tries"] = 2

    with Mocker() as mocker:
        # register responses for job and attachment submission endpoints
        mock_response = {"job_id": job_id}
        mocker.post(f"{URL}/v1/job", json=mock_response)
        mocker.post(
            f"{URL}/v1/job/{job_id}/attachments",
            [
                {"exc": requests.exceptions.ReadTimeout},
                {"exc": requests.exceptions.ReadTimeout},
            ],
        )
        mocker.post(f"{URL}/v1/job/{job_id}/action", [{"status_code": 200}])
        mocker.get(
            f"{URL}/v1/queues/fake/agents",
            json=[{"name": "fake_agent", "state": "waiting"}],
        )

        with pytest.raises(SystemExit) as exc_info:
            # use cli to submit the job (processes `sys.argv` for arguments)
            tfcli.submit()
            assert "failed to submit attachments" in exc_info.value

        # check the request history to confirm that:
        # - there is a request to the job submission endpoint
        # - there a request to the attachment submission endpoint
        history = mocker.request_history
        assert len(history) == 5
        assert history[1].path == "/v1/job"
        assert history[2].path == f"/v1/job/{job_id}/attachments"
        assert history[3].path == f"/v1/job/{job_id}/attachments"
        assert history[4].path == f"/v1/job/{job_id}/action"


def test_show(capsys, requests_mock):
    """Exercise show command."""
    jobid = str(uuid.uuid1())
    fake_return = {"job_state": "completed"}
    requests_mock.get(URL + "/v1/job/" + jobid, json=fake_return)
    sys.argv = ["", "show", jobid]
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.show()
    std = capsys.readouterr()
    assert "completed" in std.out


def test_show_yaml(capsys, requests_mock):
    """Exercise show command."""
    jobid = str(uuid.uuid1())
    fake_return = {"job_state": "completed"}
    requests_mock.get(URL + "/v1/job/" + jobid, json=fake_return)
    sys.argv = ["", "show", jobid, "--yaml"]
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.show()
    std = capsys.readouterr()
    assert "completed" in std.out


def test_results(capsys, requests_mock):
    """Results should report job_state data."""
    jobid = str(uuid.uuid1())
    fake_return = {"job_state": "completed"}
    requests_mock.get(URL + "/v1/result/" + jobid, json=fake_return)
    sys.argv = ["", "results", jobid]
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.results()
    std = capsys.readouterr()
    assert "completed" in std.out


def test_list_queues(capsys, requests_mock):
    """list_queues should report queues."""
    fake_return = {"queue1": "description1", "queue2": "description2"}
    requests_mock.get(URL + "/v1/agents/queues", json=fake_return)
    sys.argv = ["", "list-queues"]
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.list_queues()
    std = capsys.readouterr()
    assert "queue1 - description1" in std.out
    assert "queue2 - description2" in std.out


def test_list_queues_connection_error(caplog, requests_mock):
    """list_queues should report queues."""
    requests_mock.get(
        URL + "/v1/agents/queues", status_code=HTTPStatus.NOT_FOUND
    )
    sys.argv = ["", "list-queues"]
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.list_queues()
    assert "Unable to get a list of queues from the server." in caplog.text


def test_submit_no_agents_fails(capsys, tmp_path, requests_mock):
    """Test that submitting a job without online agents fails."""
    requests_mock.get(URL + "/v1/queues/fake/agents", json=[])
    fake_data = {"job_queue": "fake", "provision_data": {"distro": "fake"}}
    test_file = tmp_path / "test.json"
    test_file.write_text(json.dumps(fake_data))
    sys.argv = ["", "submit", str(test_file)]
    tfcli = testflinger_cli.TestflingerCli()
    with pytest.raises(SystemExit) as exc_info:
        tfcli.submit()
    assert exc_info.value.code == 1
    assert (
        "ERROR: No online agents available for queue fake"
        in capsys.readouterr().out
    )


def test_submit_no_agents_wait(capsys, tmp_path, requests_mock):
    """
    Test that submitting a job without online agents succeeds with
    --wait-for-available-agents.
    """
    jobid = str(uuid.uuid1())
    fake_return = {"job_id": jobid}
    requests_mock.post(URL + "/v1/job", json=fake_return)
    requests_mock.get(
        URL + "/v1/queues/fake/agents",
        json=[],
    )
    fake_data = {"job_queue": "fake", "provision_data": {"distro": "fake"}}
    test_file = tmp_path / "test.json"
    test_file.write_text(json.dumps(fake_data))
    sys.argv = ["", "submit", str(test_file), "--wait-for-available-agents"]
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.submit()
    assert (
        "WARNING: No online agents available for queue fake"
        in capsys.readouterr().out
    )


def test_submit_to_non_existing_queue(tmp_path, requests_mock):
    """Test submitting a job fails if queue does not exist."""
    jobid = str(uuid.uuid1())
    fake_queue = "fake"
    fake_return = {"job_id": jobid}
    requests_mock.post(f"{URL}/v1/job", json=fake_return)
    requests_mock.get(
        f"{URL}/v1/queues/fake/agents",
        status_code=HTTPStatus.NOT_FOUND,
        text=f"Queue '{fake_queue}' does not exist.",
    )
    fake_data = {"job_queue": fake_queue, "provision_data": {"distro": "fake"}}
    test_file = tmp_path / "test.json"
    test_file.write_text(json.dumps(fake_data))
    sys.argv = ["", "submit", str(test_file), "--wait-for-available-agents"]
    with pytest.raises(SystemExit) as exc_info:
        testflinger_cli.TestflingerCli().run()
    assert f"Queue '{fake_queue}' does not exist." in str(exc_info.value)


def test_submit_without_queue(tmp_path):
    """Test submitting a job fails if queue is not specified."""
    fake_data = {"provision_data": {"distro": "fake"}}
    test_file = tmp_path / "test.json"
    test_file.write_text(json.dumps(fake_data))
    sys.argv = ["", "submit", str(test_file)]
    with pytest.raises(SystemExit) as exc_info:
        testflinger_cli.TestflingerCli().run()
    assert "Queue was not specified in job" in str(exc_info.value)


def test_reserve(capsys, requests_mock):
    """Ensure reserve command generates correct yaml."""
    requests_mock.get(URL + "/v1/agents/queues", json={})
    requests_mock.get(URL + "/v1/agents/images/fake", json={})
    expected_yaml = (
        "job_queue: fake\n"
        "provision_data:\n"
        "    url: http://face_image.xz\n"
        "reserve_data:\n"
        "    ssh_keys:\n"
        "      - lp:fakeuser"
    )
    sys.argv = [
        "",
        "reserve",
        "-q",
        "fake",
        "-i",
        "http://face_image.xz",
        "-k",
        "lp:fakeuser",
        "-d",
    ]
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.reserve()
    std = capsys.readouterr()
    assert expected_yaml in std.out


def test_poll_serial(capsys, requests_mock):
    """Tests that serial output is polled from the correct endpoint."""
    job_id = str(uuid.uuid1())
    requests_mock.get(
        URL + f"/v1/result/{job_id}/serial_output", text="serial output"
    )
    sys.argv = ["", "poll-serial", "--oneshot", job_id]
    tfcli = testflinger_cli.TestflingerCli()
    with pytest.raises(SystemExit):
        tfcli.poll_serial()
    std = capsys.readouterr()
    assert "serial output" in std.out


def test_agent_status(capsys, requests_mock):
    """Validate that the status of the agent is retrieved."""
    fake_agent = "fake_agent"
    fake_return = {
        "name": "fake_agent",
        "queues": ["fake"],
        "state": "waiting",
        "provision_streak_count": 1,
        "provision_streak_type": "pass",
    }
    requests_mock.get(URL + "/v1/agents/data/" + fake_agent, json=fake_return)
    sys.argv = ["", "agent-status", fake_agent]
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.agent_status()
    std = capsys.readouterr()
    assert "waiting" in std.out


def test_agent_status_json(capsys, requests_mock):
    """Validate that the status of the agent is retrieved."""
    fake_agent = "fake_agent"
    fake_return = {
        "name": "fake_agent",
        "queues": ["fake"],
        "state": "waiting",
        "provision_streak_count": 1,
        "provision_streak_type": "pass",
    }
    requests_mock.get(URL + "/v1/agents/data/" + fake_agent, json=fake_return)
    sys.argv = ["", "agent-status", fake_agent, "--json"]
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.agent_status()
    std = capsys.readouterr()
    expected_out = {
        "agent": "fake_agent",
        "status": "waiting",
        "queues": ["fake"],
        "provision_streak_count": 1,
        "provision_streak_type": "pass",
    }
    assert std.out.strip() == json.dumps(expected_out, sort_keys=True)


def test_queue_status(capsys, requests_mock):
    """Validate that the status for the queue is retrieved."""
    fake_queue = "fake"
    fake_queue_data = [
        {"name": "fake_agent1", "state": "provision", "queues": ["fake"]},
        {"name": "fake_agent2", "state": "offline", "queues": ["fake"]},
    ]

    fake_job_data = [
        {
            "job_id": str(uuid.uuid1()),
            "job_state": "waiting",
            "created_at": "2023-10-13T15:22:46Z",
        },
        {
            "job_id": str(uuid.uuid1()),
            "job_state": "running",
            "created_at": "2023-10-13T15:22:40Z",
        },
        {
            "job_id": str(uuid.uuid1()),
            "job_state": "complete",
            "created_at": "2023-10-13T15:22:30Z",
        },
    ]

    requests_mock.get(
        URL + "/v1/queues/" + fake_queue + "/agents", json=fake_queue_data
    )
    requests_mock.get(
        URL + "/v1/queues/" + fake_queue + "/jobs", json=fake_job_data
    )
    sys.argv = ["", "queue-status", fake_queue]
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.queue_status()
    std = capsys.readouterr()
    assert "Agents in queue: 2" in std.out
    assert "Available:       0" in std.out
    assert "Busy:            1" in std.out
    assert "Offline:         1" in std.out
    assert "Jobs waiting:    1" in std.out
    assert "Jobs running:    1" in std.out
    assert "Jobs completed:  1" in std.out


def test_queue_status_verbose(capsys, requests_mock):
    """Test verbose queue status shows individual job details."""
    fake_queue = "fake"
    fake_queue_data = [
        {"name": "fake_agent1", "state": "provision", "queues": ["fake"]},
        {"name": "fake_agent2", "state": "offline", "queues": ["fake"]},
    ]

    fake_job_data = [
        {
            "job_id": "de153d8f-7d32-47d7-9a05-a20f2ef6bb35",
            "job_state": "waiting",
            "created_at": "2023-10-13T15:22:46Z",
        },
        {
            "job_id": "ba73620d-6d1a-45ab-bb68-a640e4e4c489",
            "job_state": "running",
            "created_at": "2023-10-13T15:22:40Z",
        },
        {
            "job_id": "8b0bb52f-08d8-4671-b275-55d84a965f7c",
            "job_state": "complete",
            "created_at": "2023-10-13T15:22:30Z",
        },
    ]

    requests_mock.get(
        URL + "/v1/queues/" + fake_queue + "/agents", json=fake_queue_data
    )
    requests_mock.get(
        URL + "/v1/queues/" + fake_queue + "/jobs", json=fake_job_data
    )
    sys.argv = ["", "queue-status", "--verbose", fake_queue]
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.queue_status()
    std = capsys.readouterr()

    # Should show agent status
    assert "Agents in queue: 2" in std.out
    assert "Available:       0" in std.out
    assert "Busy:            1" in std.out
    assert "Offline:         1" in std.out

    # Should show individual job details (no counts in verbose mode)
    assert "Jobs Waiting:" in std.out
    assert "de153d8f-7d32-47d7-9a05-a20f2ef6bb35" in std.out
    assert "Jobs Running:" in std.out
    assert "ba73620d-6d1a-45ab-bb68-a640e4e4c489" in std.out
    assert "Jobs Completed:" in std.out
    assert "8b0bb52f-08d8-4671-b275-55d84a965f7c" in std.out


def test_queue_status_json(capsys, requests_mock):
    """Test JSON output for queue status."""
    fake_queue = "fake"
    fake_queue_data = [
        {"name": "fake_agent1", "state": "provision", "queues": ["fake"]},
        {"name": "fake_agent2", "state": "offline", "queues": ["fake"]},
    ]

    fake_job_data = [
        {
            "job_id": str(uuid.uuid1()),
            "job_state": "waiting",
            "created_at": "2023-10-13T15:22:46Z",
        },
        {
            "job_id": str(uuid.uuid1()),
            "job_state": "complete",
            "created_at": "2023-10-13T15:22:30Z",
        },
    ]

    requests_mock.get(
        URL + "/v1/queues/" + fake_queue + "/agents", json=fake_queue_data
    )
    requests_mock.get(
        URL + "/v1/queues/" + fake_queue + "/jobs", json=fake_job_data
    )
    sys.argv = ["", "queue-status", "--json", fake_queue]
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.queue_status()
    std = capsys.readouterr()

    # Parse JSON output (non-verbose should only have jobs_waiting)
    output_data = json.loads(std.out)
    assert output_data["queue"] == fake_queue
    assert len(output_data["agents"]) == 2
    assert len(output_data["jobs_waiting"]) == 1
    # Non-verbose mode should only include jobs_waiting
    assert "jobs_completed" not in output_data
    assert "jobs_running" not in output_data


def test_queue_status_empty_queue(capsys, requests_mock):
    """Test queue status with no agents (original behavior)."""
    fake_queue = "empty"

    requests_mock.get(
        URL + "/v1/queues/" + fake_queue + "/agents",
        status_code=HTTPStatus.NO_CONTENT,
    )
    sys.argv = ["", "queue-status", fake_queue]
    tfcli = testflinger_cli.TestflingerCli()

    with pytest.raises(SystemExit) as exc_info:
        tfcli.queue_status()
    assert "No agent is listening on" in str(exc_info.value)


def test_queue_status_nonexistent_queue(requests_mock):
    """Test queue status with nonexistent queue (original behavior)."""
    fake_queue = "nonexistent"

    requests_mock.get(
        URL + "/v1/queues/" + fake_queue + "/agents",
        status_code=HTTPStatus.NOT_FOUND,
        text=f"Queue '{fake_queue}' does not exist.",
    )
    sys.argv = ["", "queue-status", fake_queue]
    tfcli = testflinger_cli.TestflingerCli()

    with pytest.raises(SystemExit) as exc_info:
        tfcli.queue_status()
    assert f"Queue '{fake_queue}' does not exist." in str(exc_info.value)


@pytest.mark.parametrize(
    "command", ["status", "agent-status", "queue-status", "show"]
)
def test_get_commands_fails_if_incorrect_network(command, requests_mock):
    """Test VPN errors results in SystemExit."""
    requests_mock.get(rmock.ANY, status_code=HTTPStatus.FORBIDDEN)
    # Command list is not exhaustive but indicates others will fail as well
    sys.argv = ["", command, ""]
    with pytest.raises(NetworkError) as exc_info:
        testflinger_cli.TestflingerCli().run()
    assert "Please make sure you are connected to the right network" in str(
        exc_info.value
    )
