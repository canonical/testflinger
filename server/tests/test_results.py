# Copyright (C) 2025 Canonical
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
"""Unit tests for Testflinger v1 API results endpoint."""

from datetime import datetime, timezone
from http import HTTPStatus
from io import BytesIO

import pytest
from testflinger_common.enums import LogType, TestPhase


def test_result_get_result_not_exists(mongo_app):
    """Test for 204 when getting a nonexistent result."""
    app, _ = mongo_app
    output = app.get("/v1/result/11111111-1111-1111-1111-111111111111")
    assert 204 == output.status_code


def test_result_get_bad(mongo_app):
    """Test for error when getting results from a bad job ID."""
    app, _ = mongo_app
    output = app.get("/v1/result/BAD_JOB_ID")
    assert "Invalid job_id specified" in output.text
    assert 400 == output.status_code


def test_result_post_good(mongo_app, agent_auth_header):
    """Test that posting results correctly works."""
    app, _ = mongo_app
    newjob = app.post("/v1/job", json={"job_queue": "test"})
    job_id = newjob.json.get("job_id")
    result_url = f"/v1/result/{job_id}"
    data = {"status": {"test": 404}}
    response = app.post(result_url, json=data, headers=agent_auth_header)
    assert HTTPStatus.OK == response.status_code
    assert "OK" == response.text
    response = app.get(result_url)
    assert HTTPStatus.OK == response.status_code
    assert response.json.get("test_status") == 404


def test_result_post_bad(mongo_app, agent_auth_header):
    """Test for error when posting to a bad job ID."""
    app, _ = mongo_app
    response = app.post("/v1/result/BAD_JOB_ID", headers=agent_auth_header)
    assert "Invalid job_id specified" in response.text
    assert 400 == response.status_code


def test_result_post_baddata(mongo_app, agent_auth_header):
    """Test that we get an error for posting results with no data."""
    app, _ = mongo_app
    result_url = "/v1/result/00000000-0000-0000-0000-000000000000"
    response = app.post(
        result_url, json={"foo": "bar"}, headers=agent_auth_header
    )
    assert "Validation error" in response.text
    assert 422 == response.status_code


def test_result_get_with_logs(mongo_app, agent_auth_header):
    """Tests that results are retrieved with complete output logs."""
    app, mongo = mongo_app
    newjob = app.post("/v1/job", json={"job_queue": "test"})
    job_id = newjob.json.get("job_id")
    output_url = f"/v1/result/{job_id}/log/{LogType.STANDARD_OUTPUT}"
    phase = str(TestPhase.SETUP)
    for i in range(10):
        log_data = f"line{i}\n"
        timestamp = datetime(
            2025, 4, 24, 10, 5 * i, 0, tzinfo=timezone.utc
        ).isoformat()
        log_json = {
            "fragment_number": i,
            "timestamp": timestamp,
            "phase": phase,
            "log_data": log_data,
        }
        app.post(output_url, json=log_json, headers=agent_auth_header)
    combined_log_expected = "".join([f"line{i}\n" for i in range(10)])
    result_url = f"/v1/result/{job_id}"
    data = {"status": {phase: 404}}
    response = app.post(result_url, json=data, headers=agent_auth_header)
    assert HTTPStatus.OK == response.status_code
    assert "OK" in response.text
    response = app.get(result_url)
    assert HTTPStatus.OK == response.status_code
    assert response.json[f"{phase}_output"] == combined_log_expected
    assert response.json[f"{phase}_status"] == 404


def test_artifact_post_good(mongo_app, agent_auth_header):
    """Test both get and put of a result artifact."""
    app, _ = mongo_app
    newjob = app.post("/v1/job", json={"job_queue": "test"})
    job_id = newjob.json.get("job_id")
    artifact_url = f"/v1/result/{job_id}/artifact"
    data = b"test file content"
    filedata = {"file": (BytesIO(data), "artifact.tgz")}
    output = app.post(
        artifact_url,
        data=filedata,
        content_type="multipart/form-data",
        headers=agent_auth_header,
    )
    assert "OK" == output.text
    output = app.get(artifact_url)
    assert output.data == data


def test_result_get_artifact_not_exists(mongo_app):
    """Get artifacts for a nonexistent job and confirm we get 204."""
    app, _ = mongo_app
    output = app.get(
        "/v1/result/11111111-1111-1111-1111-111111111111/artifact"
    )
    assert 204 == output.status_code


def test_job_get_result_invalid(mongo_app):
    """Test getting results with bad job UUID fails."""
    app, _ = mongo_app
    job_url = "/v1/result/00000000-0000-0000-0000-00000000000X"
    output = app.get(job_url)
    assert 400 == output.status_code


def test_job_get_result_no_data(mongo_app):
    """Test getting results for a nonexistent job."""
    app, _ = mongo_app
    job_url = "/v1/result/00000000-0000-0000-0000-000000000000"
    output = app.get(job_url)
    assert 204 == output.status_code
    assert "" == output.text


def test_result_post_payload_too_large(mongo_app, agent_auth_header):
    """Test posting large payloads to results endpoint fails."""
    app, _ = mongo_app
    newjob = app.post("/v1/job", json={"job_queue": "test"})
    job_id = newjob.json.get("job_id")

    large_data = {
        "job_state": "x" * (17 * 1024 * 1024),
        "device_info": {"test": "device"},
    }

    response = app.post(
        f"/v1/result/{job_id}", json=large_data, headers=agent_auth_header
    )
    assert "Payload too large" in response.text
    assert HTTPStatus.REQUEST_ENTITY_TOO_LARGE == response.status_code


@pytest.mark.parametrize(
    "endpoint",
    [
        "/v1/result/INVALID_UUID/log/output",
        "/v1/result/INVALID_UUID/log/serial",
    ],
)
def test_invalid_uuid_get_endpoints(mongo_app, endpoint):
    """Test that GET endpoints reject invalid UUIDs."""
    app, _ = mongo_app
    response = app.get(endpoint)

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "Invalid job" in response.text


@pytest.mark.parametrize(
    "endpoint,data",
    [
        (
            "/v1/result/INVALID_UUID/log/output",
            {
                "fragment_number": 1,
                "timestamp": "2023-01-01T00:00:00Z",
                "phase": "test",
                "log_data": "test",
            },
        )
    ],
)
def test_invalid_uuid_post_endpoints(
    mongo_app, endpoint, data, agent_auth_header
):
    """Test that POST endpoints reject invalid UUIDs."""
    app, _ = mongo_app

    if data:
        response = app.post(endpoint, json=data, headers=agent_auth_header)
    else:
        response = app.post(endpoint, data="test", headers=agent_auth_header)

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "Invalid job" in response.text
    assert "Invalid job_id" in response.text
