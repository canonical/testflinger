from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
import requests_mock as rmock
from testflinger_common.enums import AgentState

import testflinger_agent


def test_offline_handler(agent, config, server_api, requests_mock):
    """Test agent is marked for offline if signal received."""
    requests_mock.get(
        f"{server_api}/agents/data/{config['agent_id']}",
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


def test_restart_handler(agent, config, server_api, requests_mock):
    """Test agent is marked for restart if signal received."""
    requests_mock.get(
        f"{server_api}/agents/data/{config['agent_id']}",
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


def test_restart_signal_if_waiting(
    agent, config, server_api, requests_mock, caplog
):
    """Test SystemExit is received when restarting agent."""
    requests_mock.get(
        f"{server_api}/agents/data/{config['agent_id']}",
        json={"state": AgentState.RESTART, "comment": ""},
    )

    with pytest.raises(SystemExit):
        agent.process_jobs()
        assert "Restarting agent" in caplog.text
        assert (
            "Restart signal detected from supervisor process"
            in agent.status_handler.get_comment()
        )


def test_offline_agent_if_waiting(
    agent, config, server_api, requests_mock, caplog
):
    """Test Agent stop processing jobs if set to offline."""
    requests_mock.get(
        f"{server_api}/agents/data/{config['agent_id']}",
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
    agent, config, server_api, requests_mock, caplog
):
    """Test that offline status and comment takes priority over restart."""
    requests_mock.get(
        f"{server_api}/agents/data/{config['agent_id']}",
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
    agent, config, requests_mock, caplog
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
        patch.object(agent, "check_offline", side_effect=mock_check_offline),
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
    agent, config, requests_mock, caplog
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
        patch.object(agent, "check_offline", side_effect=mock_check_offline),
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
def test_agent_refresh_heartbeat(agent, config, requests_mock, state, caplog):
    """Test agent updates heartbeat at least once per defined frequency."""
    frequency = agent.heartbeat_handler.heartbeat_frequency
    # Mock last heartbeat as old
    past_heartbeat = datetime.now(timezone.utc) - timedelta(days=frequency)

    fake_agent_data = {
        "state": state,
        "comment": "",
        "queues": "fake_queue",
        "updated_at": {"$date": str(past_heartbeat)},
    }
    updated_agent_data = {
        "state": state,
        "comment": "",
        "queues": "fake_queue",
        "updated_at": {"$date": str(datetime.now(timezone.utc))},
    }

    requests_mock.post(rmock.ANY, status_code=200)
    requests_mock.get(
        rmock.ANY,
        [{"json": fake_agent_data}, {"json": updated_agent_data}],
    )

    # Set the last heartbeat to an old timestamp
    with patch.object(
        agent.heartbeat_handler,
        "_last_heartbeat",
        past_heartbeat,
    ):
        # Clear requests history from agent initialization
        requests_mock.reset_mock()
        # First call should trigger a POST to send new heartbeat
        agent.check_offline()

        # Second call should get the updated data with recent heartbeat
        agent.check_offline()
        refreshed_heartbeat = agent.heartbeat_handler._last_heartbeat

    history = requests_mock.request_history
    post_requests = [call for call in history if call.method == "POST"]
    post_data = post_requests[0].json()
    expected_data = {
        "state": fake_agent_data["state"].value,
        "comment": fake_agent_data["comment"],
    }

    # The heartbeat should have been updated
    assert past_heartbeat != refreshed_heartbeat
    # Make sure only one post request with the expected data
    assert len(post_requests) == 1
    assert post_data == expected_data
    assert "Sending heartbeat to Testflinger server" in caplog.text


@pytest.mark.parametrize("state", [AgentState.WAITING, AgentState.OFFLINE])
def test_agent_keeps_heartbeat_if_recent(
    agent, config, requests_mock, state, caplog
):
    """Test agent does not update heartbeat if not required."""
    # Mock a recent heartbeat
    recent_heartbeat = datetime.now(timezone.utc) - timedelta(hours=1)
    fake_agent_data = {
        "state": state,
        "comment": "",
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
        agent.check_offline()
        current_heartbeat = agent.heartbeat_handler._last_heartbeat

    history = requests_mock.request_history
    # Heartbeat should remain the same
    assert recent_heartbeat == current_heartbeat
    # There shouldn't be any POST request after check_offline
    assert len([call for call in history if call.method == "POST"]) == 0
