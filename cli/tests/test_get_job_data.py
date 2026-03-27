"""Unit tests for get_job_data."""

from http import HTTPStatus

import pytest

from testflinger_cli.client import Client, HTTPError

URL = "http://testflinger"


def test_get_job_data_invalid_job_id_400(requests_mock):
    """Test get_job_data with invalid job ID (HTTP 400)."""
    job_id = "invalid-job-id"
    requests_mock.get(
        f"{URL}/v1/job/{job_id}",
        status_code=HTTPStatus.BAD_REQUEST,
        json={
            "message": "Invalid job id specified. Check the job id to be sure "
            "it is correct"
        },
    )

    client = Client(URL)

    with pytest.raises(HTTPError):
        client.get_job_data(job_id)


def test_get_job_data_no_data_204(requests_mock):
    """Test get_job_data with no data (HTTP 204)."""
    job_id = "existing-but-empty-job"
    requests_mock.get(
        f"{URL}/v1/job/{job_id}",
        status_code=HTTPStatus.NO_CONTENT,
    )

    client = Client(URL)

    with pytest.raises(HTTPError):
        client.get_job_data(job_id)


def test_get_job_data_success(requests_mock):
    """Test get_job_data with valid job ID."""
    job_id = "valid-job-123"
    job_data = {"job_id": job_id, "job_state": "complete"}
    requests_mock.get(
        f"{URL}/v1/job/{job_id}", status_code=HTTPStatus.OK, json=job_data
    )

    client = Client(URL)
    result = client.get_job_data(job_id)

    assert result == job_data
