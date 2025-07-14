import os
import shutil
import tempfile
from unittest.mock import patch

import prometheus_client
import pytest
import requests_mock as rmock

import testflinger_agent
from testflinger_agent.agent import TestflingerAgent as _TestflingerAgent
from testflinger_agent.client import TestflingerClient as _TestflingerClient
from testflinger_agent.schema import validate


class TestClient:
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

    def test_offline_handler(self, agent, requests_mock):
        """Test agent is marked for offline if signal received."""
        requests_mock.get(
            f"http://127.0.0.1:8000/v1/agents/data/{self.config['agent_id']}",
            json={"state": "waiting", "comment": ""},
        )
        # Mock the status handler to simulate signal restart
        with patch.object(
            agent.status_handler, "marked_for_offline", return_value=True
        ):
            with patch.object(
                agent.status_handler,
                "get_comment",
                return_value="Offline for test",
            ):
                needs_offline, comment = agent.check_offline()

        assert needs_offline is True
        assert comment == "Offline for test"

    def test_restart_handler(self, agent, requests_mock):
        """Test agent is marked for restart if signal received."""
        requests_mock.get(
            f"http://127.0.0.1:8000/v1/agents/data/{self.config['agent_id']}",
            json={"state": "waiting", "comment": ""},
        )
        # Mock the status handler to simulate signal restart
        with patch.object(
            agent.status_handler, "marked_for_restart", return_value=True
        ):
            with patch.object(
                agent.status_handler,
                "get_comment",
                return_value="Restart signal detected from supervisor process",
            ):
                needs_restart, comment = agent.check_restart()

        assert needs_restart is True
        assert comment == "Restart signal detected from supervisor process"

    def test_restart_signal_if_waiting(self, agent, requests_mock, caplog):
        """Test SystemExit is received when restarting agent."""
        requests_mock.get(
            f"http://127.0.0.1:8000/v1/agents/data/{self.config['agent_id']}",
            json={"state": "waiting", "comment": ""},
        )
        # Mock the status handler to simulate signal restart
        agent.status_handler.update(
            comment="Restart signal detected from supervisor process",
            restart=True,
        )

        with pytest.raises(SystemExit):
            agent.process_jobs()
            assert "Restarting agent" in caplog.text

    def test_offline_agent_if_waiting(self, agent, requests_mock, caplog):
        """Test Agent stop processing jobs if set to offline."""
        requests_mock.get(
            f"http://127.0.0.1:8000/v1/agents/data/{self.config['agent_id']}",
            json={"state": "waiting", "comment": ""},
        )
        # Mock the status handler to simulate offline
        agent.status_handler.update(
            comment="Offline for test",
            offline=True,
        )

        with patch("shutil.rmtree"), patch("os.unlink"):
            agent.process_jobs()

        assert "Taking agent offline" in caplog.text
        assert agent.status_handler.comment == "Offline for test"

    def test_check_restart_offline_priority_over_restart(
        self, agent, requests_mock, caplog
    ):
        """Test that offline status and comment takes priority over restart."""
        requests_mock.get(
            f"http://127.0.0.1:8000/v1/agents/data/{self.config['agent_id']}",
            json={"state": "waiting", "comment": ""},
        )

        agent.status_handler.update(
            comment="Restart signal detected from supervisor process",
            restart=True,
        )
        agent.status_handler.update(comment="Offline for test", offline=True)

        requests_mock.post(rmock.ANY, status_code=200)
        with patch("shutil.rmtree"), patch("os.unlink"):
            agent.process_jobs()

        assert "Taking agent offline" in caplog.text
        assert agent.status_handler.needs_restart is True
        assert agent.status_handler.comment == "Offline for test"
