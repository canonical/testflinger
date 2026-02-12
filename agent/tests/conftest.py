# Copyright (C) 2024 Canonical
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>

import prometheus_client
import pytest
import requests_mock as rmock

import testflinger_agent
from testflinger_agent.agent import TestflingerAgent as _TestflingerAgent
from testflinger_agent.client import TestflingerClient as _TestflingerClient
from testflinger_agent.schema import validate


@pytest.fixture(autouse=True)
def clear_registry():
    """
    Clear Prometheus metrics so they don't get duplicated across
    test runs.
    """
    collectors = tuple(prometheus_client.REGISTRY._collector_to_names.keys())
    for collector in collectors:
        prometheus_client.REGISTRY.unregister(collector)
    yield


@pytest.fixture
def config(tmp_path):
    """Fixture of a valid agent configuration."""
    return validate(
        {
            "agent_id": "test01",
            "identifier": "12345-123456",
            "polling_interval": 2,
            "server_address": "127.0.0.1:8000",
            "job_queues": ["test"],
            "location": "nowhere",
            "provision_type": "noprovision",
            "execution_basedir": str(tmp_path),
            "logging_basedir": str(tmp_path),
            "results_basedir": str(tmp_path / "results"),
            "advertised_queues": {"test_queue": "test_queue"},
            "advertised_images": {
                "test_queue": {"test_image": "url: http://foo"}
            },
        }
    )


@pytest.fixture
def server_api(config):
    """Fixture for server api URL."""
    return f"http://{config['server_address']}/v1"


@pytest.fixture
def client(config):
    """Fixture for a TestflingerClient instance."""
    yield _TestflingerClient(config)


@pytest.fixture
def agent(config, client, requests_mock):
    """Fixture for a TestflingerAgent instance."""
    testflinger_agent.configure_logging(config)
    requests_mock.get(rmock.ANY)
    requests_mock.post(rmock.ANY)
    yield _TestflingerAgent(client)
