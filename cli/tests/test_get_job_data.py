# Copyright (C) 2026 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Unit tests for get_job_data."""

from http import HTTPStatus

import pytest

from testflinger_cli.client import HTTPError

from .conftest import URL


def test_get_job_data_invalid_job_id_400(requests_mock, client):
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

    with pytest.raises(HTTPError):
        client.get_job_data(job_id)


def test_get_job_data_no_data_204(requests_mock, client):
    """Test get_job_data with no data (HTTP 204)."""
    job_id = "existing-but-empty-job"
    requests_mock.get(
        f"{URL}/v1/job/{job_id}",
        status_code=HTTPStatus.NO_CONTENT,
    )

    with pytest.raises(HTTPError):
        client.get_job_data(job_id)


def test_get_job_data_success(requests_mock, client):
    """Test get_job_data with valid job ID."""
    job_id = "valid-job-123"
    job_data = {"job_id": job_id, "job_state": "complete"}
    requests_mock.get(
        f"{URL}/v1/job/{job_id}", status_code=HTTPStatus.OK, json=job_data
    )

    result = client.get_job_data(job_id)

    assert result == job_data
