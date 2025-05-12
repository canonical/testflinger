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

import jwt
import pytest
import requests
from requests_mock import Mocker

import testflinger_cli
from testflinger_cli.client import HTTPError
from testflinger_cli.enums import LogType
from testflinger_cli.errors import AuthorizationError

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


def test_submit_with_priority(tmp_path, requests_mock, monkeypatch):
    """Tests authorization of jobs submitted with priority."""
    job_id = str(uuid.uuid1())
    job_data = {
        "job_queue": "fake",
        "job_priority": 100,
    }
    job_file = tmp_path / "test.json"
    job_file.write_text(json.dumps(job_data))

    # Define variables for authentication
    monkeypatch.setenv("TESTFLINGER_CLIENT_ID", "my_client_id")
    monkeypatch.setenv("TESTFLINGER_SECRET_KEY", "my_secret_key")
    fake_jwt = "my_jwt"
    requests_mock.post(f"{URL}/v1/oauth2/token", text=fake_jwt)

    sys.argv = ["", "submit", str(job_file)]
    tfcli = testflinger_cli.TestflingerCli()
    mock_response = {"job_id": job_id}
    requests_mock.post(f"{URL}/v1/job", json=mock_response)
    requests_mock.get(
        URL + "/v1/queues/fake/agents",
        json=[{"name": "fake_agent", "state": "waiting"}],
    )
    tfcli.submit()
    history = requests_mock.request_history
    assert len(history) == 3
    assert history[0].path == "/v1/oauth2/token"
    assert history[2].path == "/v1/job"
    assert history[2].headers.get("Authorization") == fake_jwt


def test_submit_token_timeout_retry(tmp_path, requests_mock, monkeypatch):
    """Tests job submission retries 3 times when token has expired."""
    job_data = {
        "job_queue": "fake",
        "job_priority": 100,
    }
    job_file = tmp_path / "test.json"
    job_file.write_text(json.dumps(job_data))

    # Define variables for authentication
    monkeypatch.setenv("TESTFLINGER_CLIENT_ID", "my_client_id")
    monkeypatch.setenv("TESTFLINGER_SECRET_KEY", "my_secret_key")
    fake_jwt = "my_jwt"
    requests_mock.post(f"{URL}/v1/oauth2/token", text=fake_jwt)

    sys.argv = ["", "submit", str(job_file)]
    tfcli = testflinger_cli.TestflingerCli()
    requests_mock.post(
        f"{URL}/v1/job", text="Token has expired", status_code=401
    )
    requests_mock.get(
        URL + "/v1/queues/fake/agents",
        json=[{"name": "fake_agent", "state": "waiting"}],
    )
    with pytest.raises(SystemExit) as exc_info:
        tfcli.submit()
        assert "Token has expired" in exc_info.value

    history = requests_mock.request_history
    assert len(history) == 7
    assert history[0].path == "/v1/oauth2/token"
    assert history[2].path == "/v1/job"
    assert history[3].path == "/v1/oauth2/token"
    assert history[4].path == "/v1/job"
    assert history[5].path == "/v1/oauth2/token"
    assert history[6].path == "/v1/job"


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


def test_poll_args_generic_parsing():
    """Test that generic poll arguments are parsed correctly."""
    sys.argv = [
        "",
        "poll",
        "--oneshot",
        "--start_fragment",
        "5",
        "--start_timestamp",
        "2023-01-01T00:00:00",
        "--phase",
        "test",
        "--json",
        "test-job-id",
    ]
    tfcli = testflinger_cli.TestflingerCli()
    assert tfcli.args.oneshot is True
    assert tfcli.args.start_fragment == 5
    assert tfcli.args.start_timestamp.year == 2023
    assert tfcli.args.phase == "test"
    assert tfcli.args.json is True
    assert tfcli.args.job_id == "test-job-id"


def test_poll_serial_args_generic_parsing():
    """Test that generic poll-serial arguments are parsed correctly."""
    sys.argv = [
        "",
        "poll-serial",
        "--start_fragment",
        "10",
        "--phase",
        "provision",
        "test-job-id",
    ]
    tfcli = testflinger_cli.TestflingerCli()
    assert tfcli.args.start_fragment == 10
    assert tfcli.args.phase == "provision"
    assert tfcli.args.job_id == "test-job-id"


def test_get_combined_log_output_single_phase(requests_mock):
    """Test _get_combined_log_output for a specific phase."""
    job_id = str(uuid.uuid1())
    mock_response = {
        "output": {
            "test": {
                "last_fragment_number": 42,
                "log_data": "test phase output",
            }
        }
    }
    requests_mock.get(
        URL + f"/v1/result/{job_id}/output?start_fragment=0",
        json=mock_response,
    )

    sys.argv = ["", "poll", job_id]
    tfcli = testflinger_cli.TestflingerCli()

    last_fragment, log_data = tfcli._get_combined_log_output(
        job_id, LogType.STANDARD_OUTPUT, "test", 0, None
    )

    assert last_fragment == 42
    assert log_data == "test phase output"


def test_get_combined_log_output_all_phases(requests_mock):
    """Test _get_combined_log_output combining all phases."""
    job_id = str(uuid.uuid1())
    mock_response = {
        "output": {
            "setup": {"last_fragment_number": 10, "log_data": "setup output"},
            "test": {"last_fragment_number": 20, "log_data": "test output"},
            "cleanup": {
                "last_fragment_number": 30,
                "log_data": "cleanup output",
            },
        }
    }
    requests_mock.get(
        URL + f"/v1/result/{job_id}/output?start_fragment=0",
        json=mock_response,
    )

    sys.argv = ["", "poll", job_id]
    tfcli = testflinger_cli.TestflingerCli()

    last_fragment, log_data = tfcli._get_combined_log_output(
        job_id, LogType.STANDARD_OUTPUT, None, 0, None
    )

    assert last_fragment == 30  # max fragment number
    assert "setup output" in log_data
    assert "test output" in log_data
    assert "cleanup output" in log_data


def test_poll_output_oneshot(capsys, requests_mock):
    """Test poll command with --oneshot flag."""
    job_id = str(uuid.uuid1())
    mock_response = {
        "output": {
            "test": {"last_fragment_number": 5, "log_data": "test output data"}
        }
    }
    requests_mock.get(
        URL + f"/v1/result/{job_id}/output?start_fragment=0",
        json=mock_response,
    )

    sys.argv = ["", "poll", "--oneshot", job_id]
    tfcli = testflinger_cli.TestflingerCli()

    with pytest.raises(SystemExit):
        tfcli.poll_output()

    std = capsys.readouterr()
    assert "test output data" in std.out
    assert "Last Fragment Number: 5" in std.out


def test_poll_output_json_mode(capsys, requests_mock):
    """Test poll command with --json flag."""
    job_id = str(uuid.uuid1())
    mock_response = {
        "output": {
            "test": {"last_fragment_number": 5, "log_data": "test output data"}
        }
    }
    requests_mock.get(
        URL + f"/v1/result/{job_id}/output?start_fragment=0",
        json=mock_response,
    )

    sys.argv = ["", "poll", "--json", job_id]
    tfcli = testflinger_cli.TestflingerCli()

    with pytest.raises(SystemExit):
        tfcli.poll_output()

    std = capsys.readouterr()
    assert json.loads(std.out) == mock_response


def test_poll_serial_oneshot(capsys, requests_mock):
    """Test poll-serial command with --oneshot flag."""
    job_id = str(uuid.uuid1())
    mock_response = {
        "serial": {
            "test": {
                "last_fragment_number": 3,
                "log_data": "serial output data",
            }
        }
    }
    requests_mock.get(
        URL + f"/v1/result/{job_id}/serial_output?start_fragment=0",
        json=mock_response,
    )

    sys.argv = ["", "poll-serial", "--oneshot", job_id]
    tfcli = testflinger_cli.TestflingerCli()

    with pytest.raises(SystemExit):
        tfcli.poll_serial()

    std = capsys.readouterr()
    assert "serial output data" in std.out
    assert "Last Fragment Number: 3" in std.out


def test_poll_waiting_on_output(capsys, requests_mock):
    """Test poll command when no output is available yet."""
    job_id = str(uuid.uuid1())
    mock_response = {
        "output": {"test": {"last_fragment_number": -1, "log_data": ""}}
    }
    requests_mock.get(
        URL + f"/v1/result/{job_id}/output?start_fragment=0",
        json=mock_response,
    )

    sys.argv = ["", "poll", "--oneshot", job_id]
    tfcli = testflinger_cli.TestflingerCli()

    with pytest.raises(SystemExit):
        tfcli.poll_output()

    std = capsys.readouterr()
    assert "Waiting on Output" in std.out


def test_poll_with_start_fragment_and_timestamp(requests_mock):
    """Test poll command with start_fragment and start_timestamp parameters."""
    job_id = str(uuid.uuid1())
    start_timestamp = "2023-01-01T00:00:00"

    requests_mock.get(
        URL + f"/v1/result/{job_id}/output?"
        "start_fragment=10&start_timestamp=2023-01-01T00%3A00%3A00",
        json={
            "output": {
                "test": {"last_fragment_number": 15, "log_data": "output"}
            }
        },
    )

    sys.argv = [
        "",
        "poll",
        "--oneshot",
        "--start_fragment",
        "10",
        "--start_timestamp",
        start_timestamp,
        job_id,
    ]
    tfcli = testflinger_cli.TestflingerCli()

    # This should make the request with the correct parameters
    with pytest.raises(SystemExit):
        tfcli.poll_output()


def test_poll_with_phase_filter(requests_mock):
    """Test poll command with phase filter."""
    job_id = str(uuid.uuid1())
    mock_response = {
        "output": {
            "provision": {
                "last_fragment_number": 8,
                "log_data": "provision logs only",
            }
        }
    }
    requests_mock.get(
        URL + f"/v1/result/{job_id}/output?start_fragment=0&phase=provision",
        json=mock_response,
    )

    sys.argv = ["", "poll", "--oneshot", "--phase", "provision", job_id]
    tfcli = testflinger_cli.TestflingerCli()

    with pytest.raises(SystemExit):
        tfcli.poll_output()


def test_poll_serial(capsys, requests_mock):
    """Tests that serial output is polled from the correct endpoint."""
    job_id = str(uuid.uuid1())
    mock_response = {
        "serial": {
            "test": {"last_fragment_number": 2, "log_data": "serial output"}
        }
    }
    requests_mock.get(
        URL + f"/v1/result/{job_id}/serial_output?start_fragment=0",
        json=mock_response,
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


def test_queue_status(capsys, requests_mock):
    """Validate that the status for the queue is retrieved."""
    fake_queue = "fake"
    fake_queue_data = [
        {"name": "fake_agent1", "state": "provision", "queues": ["fake"]},
        {"name": "fake_agent2", "state": "offline", "queues": ["fake"]},
    ]

    job_id = str(uuid.uuid1())
    fake_job_data = [{"job_id": job_id, "job_state": "waiting"}]

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


def test_retrieve_regular_user_role(tmp_path, requests_mock):
    """Test that we get a regular user if no auth is made."""
    job_data = {
        "job_queue": "fake",
        "job_priority": 100,
    }
    job_file = tmp_path / "test.json"
    job_file.write_text(json.dumps(job_data))

    requests_mock.post(f"{URL}/v1/oauth2/token")
    sys.argv = ["", "submit", str(job_file)]
    tfcli = testflinger_cli.TestflingerCli()
    role = tfcli.auth.get_user_role()

    assert tfcli.auth.is_authenticated() is False
    assert role == "user"


def test_user_authenticated_with_role(tmp_path, requests_mock, monkeypatch):
    """Test user is able to authenticate and there is role defined."""
    job_data = {
        "job_queue": "fake",
        "job_priority": 100,
    }
    job_file = tmp_path / "test.json"
    job_file.write_text(json.dumps(job_data))

    # Define variables for authentication
    monkeypatch.setenv("TESTFLINGER_CLIENT_ID", "my_client_id")
    monkeypatch.setenv("TESTFLINGER_SECRET_KEY", "my_secret_key")

    expected_role = "admin"
    fake_payload = {
        "permissions": {"client_id": "my_client_id", "role": expected_role}
    }
    fake_jwt_signing_key = "my-secret"
    fake_jwt_token = jwt.encode(
        fake_payload, fake_jwt_signing_key, algorithm="HS256"
    )
    requests_mock.post(f"{URL}/v1/oauth2/token", text=fake_jwt_token)

    sys.argv = ["", "submit", str(job_file)]
    tfcli = testflinger_cli.TestflingerCli()
    role = tfcli.auth.get_user_role()

    assert tfcli.auth.is_authenticated() is True
    assert role == expected_role


def test_default_auth_user_role(tmp_path, requests_mock, monkeypatch):
    """Test we are able to get default user for legacy users."""
    job_data = {
        "job_queue": "fake",
        "job_priority": 100,
    }
    job_file = tmp_path / "test.json"
    job_file.write_text(json.dumps(job_data))

    # Define variables for authentication
    monkeypatch.setenv("TESTFLINGER_CLIENT_ID", "my_client_id")
    monkeypatch.setenv("TESTFLINGER_SECRET_KEY", "my_secret_key")

    expected_role = "contributor"
    fake_payload = {"permissions": {"client_id": "my_client_id"}}
    fake_jwt_signing_key = "my-secret"
    fake_jwt_token = jwt.encode(
        fake_payload, fake_jwt_signing_key, algorithm="HS256"
    )
    requests_mock.post(f"{URL}/v1/oauth2/token", text=fake_jwt_token)

    sys.argv = ["", "submit", str(job_file)]
    tfcli = testflinger_cli.TestflingerCli()
    role = tfcli.auth.get_user_role()

    assert tfcli.auth.is_authenticated() is True
    assert role == expected_role


def test_authorization_error(tmp_path, requests_mock, monkeypatch):
    """Test authorization error raises if received 403 from server."""
    job_data = {
        "job_queue": "fake",
        "job_priority": 100,
    }
    job_file = tmp_path / "test.json"
    job_file.write_text(json.dumps(job_data))

    # Define variables for authentication
    monkeypatch.setenv("TESTFLINGER_CLIENT_ID", "my_client_id")
    monkeypatch.setenv("TESTFLINGER_SECRET_KEY", "my_secret_key")

    requests_mock.post(
        f"{URL}/v1/oauth2/token", status_code=HTTPStatus.FORBIDDEN
    )

    sys.argv = ["", "submit", str(job_file)]
    with pytest.raises(SystemExit) as err:
        testflinger_cli.TestflingerCli()
    assert "Authorization error received from server" in str(err.value)


def test_authentication_error(tmp_path, requests_mock, monkeypatch):
    """Test authentication error raises if received 401 from server."""
    job_data = {
        "job_queue": "fake",
        "job_priority": 100,
    }
    job_file = tmp_path / "test.json"
    job_file.write_text(json.dumps(job_data))

    # Define variables for authentication
    monkeypatch.setenv("TESTFLINGER_CLIENT_ID", "my_client_id")
    monkeypatch.setenv("TESTFLINGER_SECRET_KEY", "my_secret_key")

    requests_mock.post(
        f"{URL}/v1/oauth2/token", status_code=HTTPStatus.UNAUTHORIZED
    )

    sys.argv = ["", "submit", str(job_file)]
    with pytest.raises(SystemExit) as err:
        testflinger_cli.TestflingerCli()
    assert "Authentication with Testflinger server failed" in str(err.value)


@pytest.mark.parametrize("state", ["offline", "maintenance"])
def test_set_agent_status_online(capsys, requests_mock, state, monkeypatch):
    """Validate we are able to change agent status to online."""
    fake_agent = "fake_agent"
    fake_return = {
        "name": "fake_agent",
        "queues": ["fake"],
        "state": state,
    }
    fake_send_agent_data = [{"state": "waiting", "comment": ""}]

    sys.argv = [
        "",
        "admin",
        "set",
        "agent-status",
        "--status",
        "online",
        "--agents",
        fake_agent,
    ]

    # Define variables for authentication
    monkeypatch.setenv("TESTFLINGER_CLIENT_ID", "my_client_id")
    monkeypatch.setenv("TESTFLINGER_SECRET_KEY", "my_secret_key")

    expected_role = "admin"
    fake_payload = {
        "permissions": {"client_id": "my_client_id", "role": expected_role}
    }
    fake_jwt_signing_key = "my-secret"
    fake_jwt_token = jwt.encode(
        fake_payload, fake_jwt_signing_key, algorithm="HS256"
    )
    requests_mock.post(f"{URL}/v1/oauth2/token", text=fake_jwt_token)

    requests_mock.get(URL + "/v1/agents/data/" + fake_agent, json=fake_return)
    requests_mock.post(
        URL + "/v1/agents/data/" + fake_agent, json=fake_send_agent_data
    )
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.admin_cli.set_agent_status()
    std = capsys.readouterr()
    assert "Agent fake_agent status is now: waiting" in std.out


@pytest.mark.parametrize(
    "state", ["setup", "provision", "test", "allocate", "reserve"]
)
def test_set_incorrect_agent_status(capsys, requests_mock, state, monkeypatch):
    """Validate we can't modify status to online if at any testing stage."""
    fake_agent = "fake_agent"
    fake_return = {
        "name": fake_agent,
        "queues": ["fake"],
        "state": state,
    }
    requests_mock.get(URL + "/v1/agents/data/" + fake_agent, json=fake_return)
    sys.argv = [
        "",
        "admin",
        "set",
        "agent-status",
        "--status",
        "online",
        "--agents",
        fake_agent,
    ]

    # Define variables for authentication
    monkeypatch.setenv("TESTFLINGER_CLIENT_ID", "my_client_id")
    monkeypatch.setenv("TESTFLINGER_SECRET_KEY", "my_secret_key")

    expected_role = "admin"
    fake_payload = {
        "permissions": {"client_id": "my_client_id", "role": expected_role}
    }
    fake_jwt_signing_key = "my-secret"
    fake_jwt_token = jwt.encode(
        fake_payload, fake_jwt_signing_key, algorithm="HS256"
    )
    requests_mock.post(f"{URL}/v1/oauth2/token", text=fake_jwt_token)

    tfcli = testflinger_cli.TestflingerCli()
    tfcli.admin_cli.set_agent_status()
    std = capsys.readouterr()
    assert f"Could not modify {fake_agent} in its current state" in std.out


def test_set_offline_without_comments(requests_mock, monkeypatch):
    """Validate status can't change to offline without comments."""
    fake_agent = "fake_agent"
    fake_return = {
        "name": "fake_agent",
        "queues": ["fake"],
        "state": "waiting",
    }
    requests_mock.get(URL + "/v1/agents/data/" + fake_agent, json=fake_return)
    sys.argv = [
        "",
        "admin",
        "set",
        "agent-status",
        "--status",
        "offline",
        "--agents",
        fake_agent,
    ]

    # Define variables for authentication
    monkeypatch.setenv("TESTFLINGER_CLIENT_ID", "my_client_id")
    monkeypatch.setenv("TESTFLINGER_SECRET_KEY", "my_secret_key")

    expected_role = "admin"
    fake_payload = {
        "permissions": {"client_id": "my_client_id", "role": expected_role}
    }
    fake_jwt_signing_key = "my-secret"
    fake_jwt_token = jwt.encode(
        fake_payload, fake_jwt_signing_key, algorithm="HS256"
    )
    requests_mock.post(f"{URL}/v1/oauth2/token", text=fake_jwt_token)

    tfcli = testflinger_cli.TestflingerCli()
    with pytest.raises(SystemExit) as excinfo:
        tfcli.admin_cli.set_agent_status()
    assert "Comment is required when setting agent status to offline" in str(
        excinfo.value
    )


@pytest.mark.parametrize("role", ["user", "contributor"])
def test_set_agent_status_with_unprivileged_user(
    requests_mock, monkeypatch, role
):
    """Validate status can't change if user doesn't have the right role."""
    fake_agent = "fake_agent"
    fake_return = {
        "name": "fake_agent",
        "queues": ["fake"],
        "state": "waiting",
    }
    requests_mock.get(URL + "/v1/agents/data/" + fake_agent, json=fake_return)
    sys.argv = [
        "",
        "admin",
        "set",
        "agent-status",
        "--status",
        "offline",
        "--agents",
        fake_agent,
    ]

    # Define variables for authentication
    monkeypatch.setenv("TESTFLINGER_CLIENT_ID", "my_client_id")
    monkeypatch.setenv("TESTFLINGER_SECRET_KEY", "my_secret_key")

    fake_payload = {"permissions": {"client_id": "my_client_id", "role": role}}
    fake_jwt_signing_key = "my-secret"
    fake_jwt_token = jwt.encode(
        fake_payload, fake_jwt_signing_key, algorithm="HS256"
    )
    requests_mock.post(f"{URL}/v1/oauth2/token", text=fake_jwt_token)

    tfcli = testflinger_cli.TestflingerCli()
    with pytest.raises(AuthorizationError) as excinfo:
        tfcli.admin_cli.set_agent_status()
    assert "Authorization Error: Command requires role" in str(excinfo.value)


@pytest.mark.parametrize(
    "state", ["setup", "provision", "test", "allocate", "reserve"]
)
def test_deferred_offline_message(capsys, requests_mock, state, monkeypatch):
    """Validate we receive a deffered message if agent under test phase."""
    fake_agent = "fake_agent"
    fake_return = {
        "name": fake_agent,
        "queues": ["fake"],
        "state": state,
    }
    requests_mock.get(URL + "/v1/agents/data/" + fake_agent, json=fake_return)
    sys.argv = [
        "",
        "admin",
        "set",
        "agent-status",
        "--status",
        "maintenance",
        "--agents",
        fake_agent,
    ]

    # Define variables for authentication
    monkeypatch.setenv("TESTFLINGER_CLIENT_ID", "my_client_id")
    monkeypatch.setenv("TESTFLINGER_SECRET_KEY", "my_secret_key")

    expected_role = "admin"
    fake_payload = {
        "permissions": {"client_id": "my_client_id", "role": expected_role}
    }
    fake_jwt_signing_key = "my-secret"
    fake_jwt_token = jwt.encode(
        fake_payload, fake_jwt_signing_key, algorithm="HS256"
    )
    requests_mock.post(f"{URL}/v1/oauth2/token", text=fake_jwt_token)

    fake_send_agent_data = [{"state": "maintenance", "comment": ""}]
    requests_mock.post(
        URL + "/v1/agents/data/" + fake_agent, json=fake_send_agent_data
    )
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.admin_cli.set_agent_status()
    std = capsys.readouterr()
    assert "Status maintenance deferred until job completion" in std.out


def test_set_status_unknown_agent(capsys, requests_mock, monkeypatch):
    """Validate we skip non existing agents but modify the ones that exist."""
    fake_agents = ["fake_agent1", "fake_agent2"]
    fake_return = {
        "name": "fake_agent1",
        "queues": ["fake"],
        "state": "waiting",
    }
    fake_send_agent_data = [{"state": "offline", "comment": ""}]

    sys.argv = [
        "",
        "admin",
        "set",
        "agent-status",
        "--status",
        "online",
        "--agents",
        *fake_agents,
    ]

    # Define variables for authentication
    monkeypatch.setenv("TESTFLINGER_CLIENT_ID", "my_client_id")
    monkeypatch.setenv("TESTFLINGER_SECRET_KEY", "my_secret_key")

    expected_role = "admin"
    fake_payload = {
        "permissions": {"client_id": "my_client_id", "role": expected_role}
    }
    fake_jwt_signing_key = "my-secret"
    fake_jwt_token = jwt.encode(
        fake_payload, fake_jwt_signing_key, algorithm="HS256"
    )
    requests_mock.post(f"{URL}/v1/oauth2/token", text=fake_jwt_token)

    requests_mock.get(URL + "/v1/agents/data/fake_agent1", json=fake_return)
    requests_mock.get(
        URL + "/v1/agents/data/fake_agent2", status_code=HTTPStatus.NOT_FOUND
    )
    requests_mock.post(
        URL + "/v1/agents/data/fake_agent1", json=fake_send_agent_data
    )
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.admin_cli.set_agent_status()
    std = capsys.readouterr()
    assert "Agent fake_agent1 status is now: waiting" in std.out
    assert "Agent fake_agent2 does not exist." in std.out
