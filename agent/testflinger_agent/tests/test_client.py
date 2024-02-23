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

import pytest
import uuid

import requests_mock as rmock

from testflinger_agent.client import TestflingerClient as _TestflingerClient


class TestClient:
    @pytest.fixture
    def client(self):
        config = {
            "server_address": "127.0.0.1:8000",
            "advertised_queues": {"test_queue": "test_queue"},
            "advertised_images": {
                "test_queue": {"test_image": "url: http://foo"}
            },
        }
        yield _TestflingerClient(config)

    def test_check_jobs_empty(self, client, requests_mock):
        requests_mock.get(rmock.ANY, status_code=200)
        job_data = client.check_jobs()
        assert job_data is None

    def test_check_jobs_with_job(self, client, requests_mock):
        fake_job_data = {
            "job_id": str(uuid.uuid1()),
            "job_queue": "test_queue",
        }
        requests_mock.get(rmock.ANY, json=fake_job_data)
        job_data = client.check_jobs()
        assert job_data == fake_job_data

    def test_post_advertised_queues(self, client, requests_mock):
        """
        ensure that the server api /v1/agents/queues was called with
        the correct queue data
        """
        requests_mock.post(rmock.ANY, status_code=200)
        client.post_advertised_queues()
        assert requests_mock.last_request.json() == {
            "test_queue": "test_queue"
        }

    def test_post_advertised_images(self, client, requests_mock):
        """
        ensure that the server api /v1/agents/images was called with
        the correct image data
        """
        requests_mock.post(rmock.ANY, status_code=200)
        client.post_advertised_images()
        assert requests_mock.last_request.json() == {
            "test_queue": {"test_image": "url: http://foo"}
        }
