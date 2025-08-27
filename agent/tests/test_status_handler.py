import os
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import prometheus_client
import pytest
import requests_mock as rmock
from testflinger_common.enums import AgentState

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
            json={"state": AgentState.WAITING, "comment": ""},
        )
        # Mock the status handler to simulate signal offline
        with patch.multiple(
            agent.status_handler,
            _needs_offline=True,
            _comment="Offline for test",
        ):
            needs_offline, comment = agent.check_offline()

        assert needs_offline is True
        assert comment == "Offline for test"

    def test_restart_handler(self, agent, requests_mock):
        """Test agent is marked for restart if signal received."""
        requests_mock.get(
            f"http://127.0.0.1:8000/v1/agents/data/{self.config['agent_id']}",
            json={"state": AgentState.WAITING, "comment": ""},
        )
        # Mock the status handler to simulate signal restart
        with patch.multiple(
            agent.status_handler,
            _needs_restart=True,
            _comment="Restart signal detected from supervisor process",
        ):
            needs_restart, comment = agent.check_restart()

        assert needs_restart is True
        assert comment == "Restart signal detected from supervisor process"

    def test_restart_signal_if_waiting(self, agent, requests_mock, caplog):
        """Test SystemExit is received when restarting agent."""
        requests_mock.get(
            f"http://127.0.0.1:8000/v1/agents/data/{self.config['agent_id']}",
            json={"state": AgentState.RESTART, "comment": ""},
        )

        with pytest.raises(SystemExit):
            agent.process_jobs()
            assert "Restarting agent" in caplog.text
            assert (
                "Restart signal detected from supervisor process"
                in agent.status_handler.get_comment()
            )

    def test_offline_agent_if_waiting(self, agent, requests_mock, caplog):
        """Test Agent stop processing jobs if set to offline."""
        requests_mock.get(
            f"http://127.0.0.1:8000/v1/agents/data/{self.config['agent_id']}",
            json={"state": AgentState.OFFLINE, "comment": "Offline for test"},
        )

        # Check comment is set before offline processing
        _, comment = agent.check_offline()
        assert comment == "Offline for test"

        with patch("shutil.rmtree"):
            agent.process_jobs()

        assert "Taking agent offline" in caplog.text
        assert agent.status_handler.comment == ""

    def test_check_restart_offline_priority_over_restart(
        self, agent, requests_mock, caplog
    ):
        """Test that offline status and comment takes priority over restart."""
        requests_mock.get(
            f"http://127.0.0.1:8000/v1/agents/data/{self.config['agent_id']}",
            json={"state": AgentState.WAITING, "comment": ""},
        )

        agent.status_handler.update(
            comment="Restart signal detected from supervisor process",
            restart=True,
        )
        agent.status_handler.update(comment="Offline for test", offline=True)

        # Check offline comment takes priority
        assert agent.status_handler.comment == "Offline for test"

        requests_mock.post(rmock.ANY, status_code=200)
        with patch("shutil.rmtree"):
            agent.process_jobs()

        assert "Taking agent offline" in caplog.text
        assert agent.status_handler.needs_restart is True
        assert agent.status_handler.comment == ""

    def test_agent_offline_not_processing_jobs(
        self, agent, requests_mock, caplog
    ):
        """Test device is offline and not processing any job."""
        # Mocking retrieval of agent status as offline
        mock_check_offline = [
            (True, "Offline reason"),
            (True, "Offline reason"),
        ]

        # Terminate upon first sleep
        mock_sleep = [Exception("end")]
        with (
            patch("testflinger_agent.TestflingerAgent", return_value=agent),
            patch(
                "testflinger_agent.load_config",
                return_value=agent.client.config,
            ),
            patch("testflinger_agent.parse_args") as mock_args,
            patch.object(
                agent, "check_offline", side_effect=mock_check_offline
            ),
            patch(
                "testflinger_agent.time.sleep",
                side_effect=mock_sleep,
            ),
        ):
            # Mocking args for starting agent
            mock_args.return_value.config = "fake.yaml"
            mock_args.return_value.metrics_port = 8000

            # Make sure we terminate after first agent status check
            with pytest.raises(Exception, match="end"):
                testflinger_agent.start_agent()
        assert "Agent test01 is offline, not processing jobs" in caplog.text

    def test_agent_process_job_after_offline_cleared(
        self, agent, requests_mock, caplog
    ):
        """Test agent is able to process jobs after offline is cleared."""
        # Mocking retrieval of agent status as offline
        mock_check_offline = [
            (True, "Offline reason"),
            (True, "Offline reason"),
            (False, ""),
        ]

        # Mock sleep time and terminates after first job processing.
        mock_sleep = [None, Exception("end")]
        requests_mock.post(rmock.ANY, status_code=200)
        with (
            patch("testflinger_agent.TestflingerAgent", return_value=agent),
            patch(
                "testflinger_agent.load_config",
                return_value=agent.client.config,
            ),
            patch("testflinger_agent.parse_args") as mock_args,
            patch.object(
                agent, "check_offline", side_effect=mock_check_offline
            ),
            patch("testflinger_agent.time.sleep", side_effect=mock_sleep),
            patch.object(agent, "process_jobs") as mock_process,
        ):
            # Mocking args for starting agent
            mock_args.return_value.config = "fake.yaml"
            mock_args.return_value.metrics_port = 8000

            # Make sure we terminate after processing job.
            with pytest.raises(Exception, match="end"):
                testflinger_agent.start_agent()

        assert "Agent test01 is offline, not processing jobs" in caplog.text
        assert "Checking jobs" in caplog.text
        assert mock_process.called
        assert "Sleeping for" in caplog.text

    @pytest.mark.parametrize("state", [AgentState.WAITING, AgentState.OFFLINE])
    def test_agent_refresh_heartbeat(self, agent, requests_mock, state):
        """Test agent updates heartbeat at least once per defined frequency."""
        frequency = agent.heartbeat_handler.heartbeat_frequency
        # Mock last heartbeat as old
        past_heartbeat = datetime.now(timezone.utc) - timedelta(days=frequency)

        fake_agent_data = {
            "state": state,
            "comment": "",
            "queues": "fake_queue",
            "updated_at": str(datetime.now(timezone.utc)),
        }

        requests_mock.post(rmock.ANY, status_code=200)
        requests_mock.get(rmock.ANY, json=fake_agent_data)

        # Set the last heartbeat to an old timestamp
        with patch.object(
            agent.heartbeat_handler,
            "_last_heartbeat",
            past_heartbeat,
        ):
            # This should trigger a heartbeat refresh via get_agent_state()
            agent.check_offline()
            refreshed_heartbeat = agent.heartbeat_handler._last_heartbeat

        # The heartbeat should have been updated
        assert past_heartbeat != refreshed_heartbeat

    @pytest.mark.parametrize("state", [AgentState.WAITING, AgentState.OFFLINE])
    def test_agent_keeps_heartbeat_if_recent(
        self, agent, requests_mock, state
    ):
        """Test agent does not update heartbeat if not required."""
        # Mock a recent heartbeat
        recent_heartbeat = datetime.now(timezone.utc) - timedelta(hours=1)
        fake_agent_data = {
            "state": state,
            "comment": "",
            "queues": "fake_queue",
            "updated_at": str(recent_heartbeat),
        }
        requests_mock.get(rmock.ANY, json=fake_agent_data)

        # Set the last heartbeat to recent timestamp
        with patch.object(
            agent.heartbeat_handler,
            "_last_heartbeat",
            recent_heartbeat,
        ):
            # Clear requests history from agent initialization
            requests_mock.reset_mock()
            agent.check_offline()
            current_heartbeat = agent.heartbeat_handler._last_heartbeat

        history = requests_mock.request_history
        # Heartbeat should remain the same
        assert recent_heartbeat == current_heartbeat
        # There shouldn't be any POST request after check_offline
        assert len([call for call in history if call.method == "POST"]) == 0
