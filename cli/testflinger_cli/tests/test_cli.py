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

"""
Unit tests for testflinger-cli
"""

import json
import re
import sys
import tarfile
import uuid

import pytest
import requests
from requests_mock import Mocker

import testflinger_cli
from testflinger_cli.client import HTTPError


URL = "https://testflinger.canonical.com"


def test_status(capsys, requests_mock):
    """Status should report job_state data"""
    jobid = str(uuid.uuid1())
    fake_return = {"job_state": "completed"}
    requests_mock.get(URL + "/v1/result/" + jobid, json=fake_return)
    sys.argv = ["", "status", jobid]
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.status()
    std = capsys.readouterr()
    assert std.out == "completed\n"


def test_cancel_503(requests_mock):
    """Cancel should fail loudly if cancel action returns 503"""
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
    """Cancel should fail if /v1/job/<job_id>/action URL returns 400 code"""
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
    """Make sure jobid is read back from submitted job"""
    jobid = str(uuid.uuid1())
    fake_data = {"queue": "fake", "provision_data": {"distro": "fake"}}
    testfile = tmp_path / "test.json"
    testfile.write_text(json.dumps(fake_data))
    fake_return = {"job_id": jobid}
    requests_mock.post(URL + "/v1/job", json=fake_return)
    sys.argv = ["", "submit", str(testfile)]
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.submit()
    std = capsys.readouterr()
    assert jobid in std.out


def test_submit_bad_data(tmp_path, requests_mock):
    """Ensure a 422 response from bad data shows the returned errors"""
    fake_data = {"badkey": "badvalue"}
    testfile = tmp_path / "test.json"
    testfile.write_text(json.dumps(fake_data))
    # return 422 and "expected error"
    requests_mock.post(URL + "/v1/job", status_code=422, text="expected error")
    sys.argv = ["", "submit", str(testfile)]
    tfcli = testflinger_cli.TestflingerCli()
    with pytest.raises(SystemExit) as err:
        tfcli.submit()
    assert (
        "Unexpected error status from testflinger server: [422] expected error"
        in err.value.code
    )


def test_submit_with_attachments(tmp_path):
    """Make sure jobs with attachments are submitted correctly"""

    job_id = str(uuid.uuid1())
    job_file = tmp_path / "test.json"
    job_data = {
        "queue": "fake",
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

        # use cli to submit the job (processes `sys.argv` for arguments)
        tfcli.submit()

        # check the request history to confirm that:
        # - there is a request to the job submission endpoint
        # - there a request to the attachment submission endpoint
        history = mocker.request_history
        assert len(history) == 2
        assert history[0].path == "/v1/job"
        assert history[1].path == f"/v1/job/{job_id}/attachments"

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
    """Check retries after unsuccessful attachment submissions"""

    job_id = str(uuid.uuid1())
    job_file = tmp_path / "test.json"
    job_data = {
        "queue": "fake",
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

        # use cli to submit the job (processes `sys.argv` for arguments)
        tfcli.submit()

        # check the request history to confirm that:
        # - there is a request to the job submission endpoint
        # - there are repeated requests to the attachment submission endpoint
        history = mocker.request_history
        assert len(history) == 5
        assert history[0].path == "/v1/job"
        for entry in history[1:]:
            assert entry.path == f"/v1/job/{job_id}/attachments"


def test_submit_attachments_no_retries(tmp_path):
    """Check no retries after attachment submission fails unrecoverably"""

    job_id = str(uuid.uuid1())
    job_file = tmp_path / "test.json"
    job_data = {
        "queue": "fake",
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
        assert len(history) == 3
        assert history[0].path == "/v1/job"
        assert history[1].path == f"/v1/job/{job_id}/attachments"
        assert history[2].path == f"/v1/job/{job_id}/action"


def test_submit_attachments_timeout(tmp_path):
    """Make timeout after repeated attachment submission timeouts"""

    job_id = str(uuid.uuid1())
    job_file = tmp_path / "test.json"
    job_data = {
        "queue": "fake",
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

        with pytest.raises(SystemExit) as exc_info:
            # use cli to submit the job (processes `sys.argv` for arguments)
            tfcli.submit()
            assert "failed to submit attachments" in exc_info.value

        # check the request history to confirm that:
        # - there is a request to the job submission endpoint
        # - there a request to the attachment submission endpoint
        history = mocker.request_history
        assert len(history) == 4
        assert history[0].path == "/v1/job"
        assert history[1].path == f"/v1/job/{job_id}/attachments"
        assert history[2].path == f"/v1/job/{job_id}/attachments"
        assert history[3].path == f"/v1/job/{job_id}/action"


def test_show(capsys, requests_mock):
    """Exercise show command"""
    jobid = str(uuid.uuid1())
    fake_return = {"job_state": "completed"}
    requests_mock.get(URL + "/v1/job/" + jobid, json=fake_return)
    sys.argv = ["", "show", jobid]
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.show()
    std = capsys.readouterr()
    assert "completed" in std.out


def test_results(capsys, requests_mock):
    """results should report job_state data"""
    jobid = str(uuid.uuid1())
    fake_return = {"job_state": "completed"}
    requests_mock.get(URL + "/v1/result/" + jobid, json=fake_return)
    sys.argv = ["", "results", jobid]
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.results()
    std = capsys.readouterr()
    assert "completed" in std.out


def test_list_queues(capsys, requests_mock):
    """list_queues should report queues"""
    fake_return = {"queue1": "description1", "queue2": "description2"}
    requests_mock.get(URL + "/v1/agents/queues", json=fake_return)
    sys.argv = ["", "list-queues"]
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.list_queues()
    std = capsys.readouterr()
    assert "queue1 - description1" in std.out
    assert "queue2 - description2" in std.out


def test_list_queues_connection_error(caplog, requests_mock):
    """list_queues should report queues"""
    requests_mock.get(URL + "/v1/agents/queues", status_code=400)
    sys.argv = ["", "list-queues"]
    tfcli = testflinger_cli.TestflingerCli()
    with pytest.raises(SystemExit):
        tfcli.list_queues()
    assert "Unable to get a list of queues from the server." in caplog.text
