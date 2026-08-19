import os
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import prometheus_client
import pytest
import requests_mock as rmock
from testflinger_common.enums import AgentMode, AgentState

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
            json={"mode": AgentMode.ONLINE, "state": AgentState.WAITING},
        )
        with patch.multiple(
            agent.status_handler,
            _needs_offline=True,
            _comment="Offline for test",
        ):
            mode, comment = agent.check_mode_change()

        assert mode == AgentMode.MAINTENANCE
        assert comment == "Offline for test"

    def test_restart_handler(self, agent, requests_mock):
        """Test agent is marked for restart if signal received."""
        requests_mock.get(
            f"http://127.0.0.1:8000/v1/agents/data/{self.config['agent_id']}",
            json={"mode": AgentMode.ONLINE, "state": AgentState.WAITING},
        )
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
            json={"mode": AgentMode.RESTART},
        )

        with pytest.raises(SystemExit):
            agent.process_jobs()
            assert "Restarting agent" in caplog.text
            assert (
                "Restart signal detected from supervisor process"
                in agent.status_handler.get_comment()
            )

    def test_enter_maintenance_mode_if_waiting(
        self, agent, requests_mock, caplog
    ):
        """Test agent stops processing jobs if set to maintenance."""
        requests_mock.get(
            f"http://127.0.0.1:8000/v1/agents/data/{self.config['agent_id']}",
            json={
                "mode": AgentMode.MAINTENANCE,
                "comment": "Offline for test",
            },
        )

        _, comment = agent.check_mode_change()
        assert comment == "Offline for test"

        with patch("shutil.rmtree"):
            agent.process_jobs()

        assert "Entering maintenance mode" in caplog.text
        assert agent.status_handler.comment == ""

    def test_check_restart_offline_priority_over_restart(
        self, agent, requests_mock, caplog
    ):
        """Test that offline status and comment takes priority over restart."""
        requests_mock.get(
            f"http://127.0.0.1:8000/v1/agents/data/{self.config['agent_id']}",
            json={"mode": AgentMode.ONLINE, "state": AgentState.WAITING},
        )

        agent.status_handler.update(
            comment="Restart signal detected from supervisor process",
            restart=True,
        )
        agent.status_handler.update(comment="Offline for test", offline=True)

        assert agent.status_handler.comment == "Offline for test"

        requests_mock.post(rmock.ANY, status_code=200)
        with patch("shutil.rmtree"):
            agent.process_jobs()

        assert "Entering maintenance mode" in caplog.text
        assert agent.status_handler.needs_restart is True
        assert agent.status_handler.comment == ""

    def test_agent_offline_not_processing_jobs(
        self, agent, requests_mock, caplog, tmp_path
    ):
        """Test device is offline and not processing any job."""
        # Mocking retrieval of agent status as offline.
        # New loop design: check_mode_change is called once per outer
        # iteration.
        # First call sees offline → enter maintenance, then sleep raises.
        mock_check_offline = [
            (AgentMode.MAINTENANCE, "Offline reason"),
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
                agent, "check_mode_change", side_effect=mock_check_offline
            ),
            patch(
                "testflinger_agent.time.sleep",
                side_effect=mock_sleep,
            ),
        ):
            # Mocking args for starting agent
            mock_args.return_value.config = "fake.yaml"
            mock_args.return_value.metrics_port = 8000
            mock_args.return_value.token_file = f"{tmp_path}/test_token"

            # Make sure we terminate after first agent status check
            with pytest.raises(Exception, match="end"):
                testflinger_agent.start_agent()
        assert (
            "Agent test01 is in maintenance mode, not processing normal jobs!"
            in caplog.text
        )

    def test_agent_process_job_after_offline_cleared(
        self, agent, requests_mock, caplog, tmp_path
    ):
        """Test agent is able to process jobs after offline is cleared."""
        # New loop design: each outer iteration calls check_mode_change once.
        # Iter 1: offline → enter maintenance, sleep.
        # Iter 2: still offline → stay in maintenance, sleep.
        # Iter 3: online → exit maintenance, process_jobs, sleep(raises).
        mock_check_offline = [
            (AgentMode.MAINTENANCE, "Offline reason"),
            (AgentMode.MAINTENANCE, "Offline reason"),
            (AgentMode.ONLINE, ""),
        ]

        # Mock sleep time: two maintenance-loop sleeps, then raises on job
        # loop.
        mock_sleep = [None, None, Exception("end")]
        requests_mock.post(rmock.ANY, status_code=200)
        with (
            patch("testflinger_agent.TestflingerAgent", return_value=agent),
            patch(
                "testflinger_agent.load_config",
                return_value=agent.client.config,
            ),
            patch("testflinger_agent.parse_args") as mock_args,
            patch.object(
                agent, "check_mode_change", side_effect=mock_check_offline
            ),
            patch("testflinger_agent.time.sleep", side_effect=mock_sleep),
            patch.object(agent, "process_jobs") as mock_process,
        ):
            # Mocking args for starting agent
            mock_args.return_value.config = "fake.yaml"
            mock_args.return_value.metrics_port = 8000
            mock_args.return_value.token_file = f"{tmp_path}/test_token"

            # Make sure we terminate after processing job.
            with pytest.raises(Exception, match="end"):
                testflinger_agent.start_agent()

        assert (
            "Agent test01 is in maintenance mode, not processing normal jobs!"
            in caplog.text
        )
        assert "exiting maintenance mode" in caplog.text
        assert "Checking jobs" in caplog.text
        assert mock_process.called
        assert "Sleeping for" in caplog.text

    @pytest.mark.parametrize(
        "mode",
        [
            AgentMode.ONLINE,
            AgentMode.OFFLINE,
            AgentMode.MAINTENANCE,
            AgentMode.RESTART,
        ],
    )
    def test_agent_refresh_heartbeat(self, agent, requests_mock, mode, caplog):
        """Test agent updates heartbeat at least once per defined frequency.

        Modes with a sub-state (ONLINE, MAINTENANCE) should re-post state.
        Modes without a sub-state (OFFLINE, RESTART) should post nothing.
        """
        frequency = agent.heartbeat_handler.heartbeat_frequency
        past_heartbeat = datetime.now(timezone.utc) - timedelta(days=frequency)

        has_substate = mode in (AgentMode.ONLINE, AgentMode.MAINTENANCE)
        fake_agent_data = {
            "mode": mode,
            "state": AgentState.WAITING if has_substate else None,
            "queues": "fake_queue",
            "updated_at": {"$date": str(past_heartbeat)},
        }
        updated_agent_data = {
            "mode": mode,
            "state": AgentState.WAITING if has_substate else None,
            "queues": "fake_queue",
            "updated_at": {"$date": str(datetime.now(timezone.utc))},
        }

        requests_mock.post(rmock.ANY, status_code=200)
        requests_mock.get(
            rmock.ANY,
            [{"json": fake_agent_data}, {"json": updated_agent_data}],
        )

        with patch.object(
            agent.heartbeat_handler,
            "_last_heartbeat",
            past_heartbeat,
        ):
            requests_mock.reset_mock()
            agent.check_mode_change()
            agent.check_mode_change()
            refreshed_heartbeat = agent.heartbeat_handler._last_heartbeat

        history = requests_mock.request_history
        post_requests = [call for call in history if call.method == "POST"]

        # Heartbeat only re-posts state (sub-state), not mode or comment
        if fake_agent_data.get("state"):
            expected_data = {"state": fake_agent_data["state"].value}
            assert past_heartbeat != refreshed_heartbeat
            assert len(post_requests) == 1
            assert (
                post_data == expected_data
                if (post_data := post_requests[0].json())
                else True
            )
            assert "Sending heartbeat to Testflinger server" in caplog.text
        else:
            # offline mode — no sub-state to heartbeat
            assert len(post_requests) == 0

    @pytest.mark.parametrize(
        "mode",
        [
            AgentMode.ONLINE,
            AgentMode.OFFLINE,
            AgentMode.MAINTENANCE,
            AgentMode.RESTART,
        ],
    )
    def test_agent_keeps_heartbeat_if_recent(self, agent, requests_mock, mode):
        """Test agent does not update heartbeat if not required."""
        recent_heartbeat = datetime.now(timezone.utc) - timedelta(hours=1)
        has_substate = mode in (AgentMode.ONLINE, AgentMode.MAINTENANCE)
        fake_agent_data = {
            "mode": mode,
            "state": AgentState.WAITING if has_substate else None,
            "queues": "fake_queue",
            "updated_at": {"$date": str(recent_heartbeat)},
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
            agent.check_mode_change()
            current_heartbeat = agent.heartbeat_handler._last_heartbeat

        history = requests_mock.request_history
        # Heartbeat should remain the same
        assert recent_heartbeat == current_heartbeat
        # There shouldn't be any POST request after check_mode_change
        assert len([call for call in history if call.method == "POST"]) == 0


class TestMaintenanceMode:
    """Tests for maintenance mode transitions and queue management."""

    @pytest.fixture(autouse=True)
    def clear_registry(self):
        """Clear Prometheus metrics between test runs."""
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
                "job_queues": ["queue-a", "queue-b"],
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
        shutil.rmtree(self.tmpdir)

    def _posted_queues(self, requests_mock):
        """Return the list of queue payloads POSTed to the agents/data
        endpoint.
        """
        agent_data_url = (
            f"http://127.0.0.1:8000/v1/agents/data/{self.config['agent_id']}"
        )
        return [
            call.json().get("queues")
            for call in requests_mock.request_history
            if call.method == "POST"
            and call.url == agent_data_url
            and "queues" in (call.json() or {})
        ]

    def test_enter_maintenance_mode_sets_maintenance_mode(
        self, agent, requests_mock, caplog
    ):
        """Entering maintenance mode should post MAINTENANCE mode."""
        requests_mock.reset_mock()
        agent.enter_maintenance_mode("planned maintenance")

        agent_data_url = (
            f"http://127.0.0.1:8000/v1/agents/data/{self.config['agent_id']}"
        )
        mode_posts = [
            call.json()
            for call in requests_mock.request_history
            if call.method == "POST"
            and call.url == agent_data_url
            and "mode" in (call.json() or {})
        ]
        assert any(
            p.get("mode") == AgentMode.MAINTENANCE for p in mode_posts
        ), f"Expected MAINTENANCE mode to be posted; got: {mode_posts}"
        assert "Entering maintenance mode" in caplog.text

    def test_enter_maintenance_mode_sets_maintenance_queue(
        self, agent, requests_mock
    ):
        """Entering maintenance mode posts <agent>_maintenance as the only
        queue the agent will monitor for jobs.

        This is distinct from "advertising" a queue in the Testflinger sense.
        The agent tells the server which queues it is listening on; during
        maintenance that is restricted to the single <agent_id>_maintenance
        queue so that only purpose-sent maintenance jobs can reach it.
        """
        requests_mock.reset_mock()
        agent.enter_maintenance_mode()

        posted = self._posted_queues(requests_mock)
        assert posted, "Expected at least one queues POST"
        # The last queues update should be the maintenance queue only
        last_queues = posted[-1]
        assert last_queues == ["test01_maintenance"], (
            f"Expected ['test01_maintenance'], got {last_queues}"
        )

    def test_exit_maintenance_mode_restores_normal_queues(
        self, agent, requests_mock
    ):
        """Exiting maintenance mode must restore the original job_queues."""
        requests_mock.reset_mock()
        agent.exit_maintenance_mode()

        posted = self._posted_queues(requests_mock)
        assert posted, "Expected at least one queues POST after exit"
        last_queues = posted[-1]
        assert last_queues == [
            "queue-a",
            "queue-b",
        ], f"Expected original queues restored, got {last_queues}"

    def test_exit_maintenance_mode_sets_online_mode(
        self, agent, requests_mock
    ):
        """Exiting maintenance mode posts ONLINE mode and WAITING state."""
        requests_mock.reset_mock()
        agent.exit_maintenance_mode()

        agent_data_url = (
            f"http://127.0.0.1:8000/v1/agents/data/{self.config['agent_id']}"
        )
        mode_posts = [
            call.json()
            for call in requests_mock.request_history
            if call.method == "POST"
            and call.url == agent_data_url
            and "mode" in (call.json() or {})
        ]
        assert any(p.get("mode") == AgentMode.ONLINE for p in mode_posts), (
            f"Expected ONLINE mode after exit; got: {mode_posts}"
        )
        state_posts = [
            call.json()
            for call in requests_mock.request_history
            if call.method == "POST"
            and call.url == agent_data_url
            and "state" in (call.json() or {})
        ]
        assert any(
            p.get("state") == AgentState.WAITING for p in state_posts
        ), f"Expected WAITING state after exit; got: {state_posts}"

    def test_enter_maintenance_mode_sets_mode_and_restricts_queues(
        self, agent, requests_mock, caplog
    ):
        """enter_maintenance_mode() should set MAINTENANCE mode and restrict
        queues, not set OFFLINE.
        """
        requests_mock.reset_mock()
        agent.enter_maintenance_mode("recovery failed")

        agent_data_url = (
            f"http://127.0.0.1:8000/v1/agents/data/{self.config['agent_id']}"
        )
        mode_posts = [
            call.json()
            for call in requests_mock.request_history
            if call.method == "POST"
            and call.url == agent_data_url
            and "mode" in (call.json() or {})
        ]
        modes = [p.get("mode") for p in mode_posts]
        assert AgentMode.MAINTENANCE in modes, (
            "Expected MAINTENANCE mode on enter_maintenance_mode(); "
            f"got modes: {modes}"
        )
        assert AgentMode.OFFLINE not in modes, (
            "OFFLINE mode should not be set by enter_maintenance_mode()"
        )
        posted_queues = self._posted_queues(requests_mock)
        assert ["test01_maintenance"] in posted_queues

    def test_maintenance_transition_online_to_maintenance_to_online(
        self, agent, requests_mock, caplog, tmp_path
    ):
        """Full cycle: online → maintenance → online restores queues."""
        # New loop design: one check_mode_change call per outer iteration.
        # Iter 1: offline → enter maintenance, sleep.
        # Iter 2: still offline → stay in maintenance, sleep.
        # Iter 3: online → exit maintenance, process_jobs, sleep(raises).
        mock_check_offline = [
            (AgentMode.MAINTENANCE, "Scheduled maintenance"),
            (AgentMode.MAINTENANCE, "Scheduled maintenance"),
            (AgentMode.ONLINE, ""),
        ]
        mock_sleep = [None, None, Exception("end")]
        requests_mock.post(rmock.ANY, status_code=200)

        with (
            patch("testflinger_agent.TestflingerAgent", return_value=agent),
            patch(
                "testflinger_agent.load_config",
                return_value=agent.client.config,
            ),
            patch("testflinger_agent.parse_args") as mock_args,
            patch.object(
                agent, "check_mode_change", side_effect=mock_check_offline
            ),
            patch("testflinger_agent.time.sleep", side_effect=mock_sleep),
            patch.object(agent, "process_jobs"),
        ):
            mock_args.return_value.config = "fake.yaml"
            mock_args.return_value.metrics_port = None
            mock_args.return_value.token_file = f"{tmp_path}/test_token"

            with pytest.raises(Exception, match="end"):
                testflinger_agent.start_agent()

        assert "Entering maintenance mode" in caplog.text
        assert "Exiting maintenance mode" in caplog.text

        # After exiting maintenance, the last queues post should be the
        # normal job_queues restored
        posted_queues = self._posted_queues(requests_mock)
        assert posted_queues, "No queues were posted at all"
        assert posted_queues[-1] == [
            "queue-a",
            "queue-b",
        ], f"Last queues post should restore original; got: {posted_queues}"

    def test_maintenance_mode_queues_not_restored_while_still_in_maintenance(
        self, agent, requests_mock, caplog, tmp_path
    ):
        """If agent stays in maintenance, queues should not be restored."""
        mock_check_offline = [
            (AgentMode.MAINTENANCE, "Maintenance"),
            (AgentMode.MAINTENANCE, "Maintenance"),
        ]
        # Raise immediately to stop the inner while loop after first check
        mock_sleep = [Exception("end")]

        with (
            patch("testflinger_agent.TestflingerAgent", return_value=agent),
            patch(
                "testflinger_agent.load_config",
                return_value=agent.client.config,
            ),
            patch("testflinger_agent.parse_args") as mock_args,
            patch.object(
                agent, "check_mode_change", side_effect=mock_check_offline
            ),
            patch("testflinger_agent.time.sleep", side_effect=mock_sleep),
        ):
            mock_args.return_value.config = "fake.yaml"
            mock_args.return_value.metrics_port = None
            mock_args.return_value.token_file = f"{tmp_path}/test_token"

            # Reset mock history so only this test's requests are tracked
            requests_mock.reset_mock()
            with pytest.raises(Exception, match="end"):
                testflinger_agent.start_agent()

        assert "Exiting maintenance mode" not in caplog.text
        # Normal queues must NOT be posted while still in maintenance
        posted_queues = self._posted_queues(requests_mock)
        for q in posted_queues:
            assert q != [
                "queue-a",
                "queue-b",
            ], (
                "Normal queues should not be restored while still in "
                "maintenance"
            )

    def test_enter_maintenance_not_called_twice_on_consecutive_offline_polls(
        self, agent, requests_mock, caplog, tmp_path
    ):
        """enter_maintenance_mode must be called exactly once across
        consecutive offline poll cycles; the outer loop must not
        re-enter maintenance on every iteration once already in
        maintenance state.
        """
        mock_check_offline = [
            (AgentMode.MAINTENANCE, "Maintenance"),
            (AgentMode.MAINTENANCE, "Maintenance"),
            (AgentMode.ONLINE, ""),
        ]
        mock_sleep = [None, None, Exception("end")]
        requests_mock.post(rmock.ANY, status_code=200)

        enter_calls = []

        original_enter = agent.enter_maintenance_mode

        def counting_enter(comment=""):
            enter_calls.append(comment)
            return original_enter(comment)

        with (
            patch("testflinger_agent.TestflingerAgent", return_value=agent),
            patch(
                "testflinger_agent.load_config",
                return_value=agent.client.config,
            ),
            patch("testflinger_agent.parse_args") as mock_args,
            patch.object(
                agent, "check_mode_change", side_effect=mock_check_offline
            ),
            patch.object(
                agent, "enter_maintenance_mode", side_effect=counting_enter
            ),
            patch("testflinger_agent.time.sleep", side_effect=mock_sleep),
            patch.object(agent, "process_jobs"),
        ):
            mock_args.return_value.config = "fake.yaml"
            mock_args.return_value.metrics_port = None
            mock_args.return_value.token_file = f"{tmp_path}/test_token"

            with pytest.raises(Exception, match="end"):
                testflinger_agent.start_agent()

        assert len(enter_calls) == 1, (
            f"enter_maintenance_mode should be called exactly once, "
            f"got {len(enter_calls)} calls"
        )

    def test_exit_maintenance_not_called_if_never_entered(
        self, agent, requests_mock, caplog, tmp_path
    ):
        """exit_maintenance_mode must never be called if the agent was
        already online throughout the outer loop.
        """
        mock_check_offline = [
            (AgentMode.ONLINE, ""),
        ]
        mock_sleep = [Exception("end")]
        requests_mock.post(rmock.ANY, status_code=200)

        exit_calls = []

        def counting_exit():
            exit_calls.append(True)

        with (
            patch("testflinger_agent.TestflingerAgent", return_value=agent),
            patch(
                "testflinger_agent.load_config",
                return_value=agent.client.config,
            ),
            patch("testflinger_agent.parse_args") as mock_args,
            patch.object(
                agent, "check_mode_change", side_effect=mock_check_offline
            ),
            patch.object(
                agent, "exit_maintenance_mode", side_effect=counting_exit
            ),
            patch("testflinger_agent.time.sleep", side_effect=mock_sleep),
            patch.object(agent, "process_jobs"),
        ):
            mock_args.return_value.config = "fake.yaml"
            mock_args.return_value.metrics_port = None
            mock_args.return_value.token_file = f"{tmp_path}/test_token"

            with pytest.raises(Exception, match="end"):
                testflinger_agent.start_agent()

        assert len(exit_calls) == 0, (
            "exit_maintenance_mode should not be called if agent was "
            "never in maintenance"
        )

    def test_rapid_maintenance_transition_within_single_interval(
        self, agent, requests_mock, caplog, tmp_path
    ):
        """If maintenance starts and clears within a single polling interval
        the loop must still call enter then exit exactly once each.
        """
        # Iter 1: see offline for first time → enter maintenance, sleep.
        # Iter 2: already cleared → exit maintenance, process jobs,
        # sleep(raises).
        mock_check_offline = [
            (AgentMode.MAINTENANCE, "Brief maintenance"),
            (AgentMode.ONLINE, ""),
        ]
        mock_sleep = [None, Exception("end")]
        requests_mock.post(rmock.ANY, status_code=200)

        enter_calls = []
        exit_calls = []

        original_enter = agent.enter_maintenance_mode
        original_exit = agent.exit_maintenance_mode

        def counting_enter(comment=""):
            enter_calls.append(comment)
            return original_enter(comment)

        def counting_exit():
            exit_calls.append(True)
            return original_exit()

        with (
            patch("testflinger_agent.TestflingerAgent", return_value=agent),
            patch(
                "testflinger_agent.load_config",
                return_value=agent.client.config,
            ),
            patch("testflinger_agent.parse_args") as mock_args,
            patch.object(
                agent, "check_mode_change", side_effect=mock_check_offline
            ),
            patch.object(
                agent, "enter_maintenance_mode", side_effect=counting_enter
            ),
            patch.object(
                agent, "exit_maintenance_mode", side_effect=counting_exit
            ),
            patch("testflinger_agent.time.sleep", side_effect=mock_sleep),
            patch.object(agent, "process_jobs"),
        ):
            mock_args.return_value.config = "fake.yaml"
            mock_args.return_value.metrics_port = None
            mock_args.return_value.token_file = f"{tmp_path}/test_token"

            with pytest.raises(Exception, match="end"):
                testflinger_agent.start_agent()

        assert len(enter_calls) == 1, "enter_maintenance_mode called once"
        assert len(exit_calls) == 1, "exit_maintenance_mode called once"
