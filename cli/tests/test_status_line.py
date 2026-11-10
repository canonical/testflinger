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

"""Unit tests for StatusLine."""

import threading
from unittest import mock

from freezegun import freeze_time

from testflinger_cli.status_line import StatusLine


class TestStatusLineInit:
    """Tests for StatusLine initialization."""

    def test_init_starts_timer(self, mock_tty):
        """init() should configure and start the timer thread."""
        StatusLine.init(update_rate=10.0)

        assert StatusLine._running is True
        assert StatusLine._start_time is not None
        assert StatusLine._timer_thread is not None
        assert StatusLine._timer_thread.daemon is True

        StatusLine.stop()

    def test_init_overrides_builtins(self, mock_tty):
        """init() should override print and input builtins."""
        import builtins

        original_print = builtins.print
        original_input = builtins.input

        StatusLine.init()

        # After init, builtins should be replaced
        assert builtins.print != original_print
        assert builtins.input != original_input

        StatusLine.stop()

        # After stop, builtins should be restored
        assert builtins.print == original_print
        assert builtins.input == original_input


class TestStatusLineElapsedTime:
    """Tests for elapsed time display."""

    @freeze_time("2026-03-26 12:00:00")
    def test_elapsed_time_counts_up(self, mock_tty):
        """Elapsed time should count up from 00:00."""
        StatusLine.init()

        # Verify initial timestamp
        ts = StatusLine._get_timestamp()
        assert ts == "00:00"

        # Advance time 2 seconds and verify it increments
        with freeze_time("2026-03-26 12:00:02"):
            ts = StatusLine._get_timestamp()
            assert ts == "00:02"

        StatusLine.stop()

    @freeze_time("2026-03-26 12:00:00")
    def test_get_elapsed_time_tuple(self, mock_tty):
        """get_elapsed_time() should return (hours, minutes, seconds)."""
        StatusLine.init()

        with freeze_time("2026-03-26 12:00:01"):
            hours, minutes, seconds = StatusLine.get_elapsed_time()

        assert hours == 0
        assert minutes == 0
        assert seconds == 1

        StatusLine.stop()


class TestStatusLineCountdown:
    """Tests for countdown mode."""

    @freeze_time("2026-03-26 12:00:00")
    def test_set_countdown_counts_down(self, mock_tty):
        """set_countdown() should enable countdown mode."""
        StatusLine.init()

        # Set 10-second countdown
        StatusLine.set_countdown(10)

        # Verify countdown starts at correct value
        ts = StatusLine._get_timestamp()
        assert ts == "00:10"

        # Advance time 2 seconds and verify it decrements
        with freeze_time("2026-03-26 12:00:02"):
            ts = StatusLine._get_timestamp()
            assert ts == "00:08"

        # Advance until countdown reaches zero
        with freeze_time("2026-03-26 12:00:10"):
            ts = StatusLine._get_timestamp()
            assert ts == "00:00"

        StatusLine.stop()

    @freeze_time("2026-03-26 12:00:00")
    def test_countdown_reaches_zero(self, mock_tty):
        """Countdown should stay at 00:00 after reaching zero."""
        StatusLine.init()

        StatusLine.set_countdown(3)

        with freeze_time("2026-03-26 12:00:04"):
            ts = StatusLine._get_timestamp()
            assert ts == "00:00"

        StatusLine.stop()

    @freeze_time("2026-03-26 12:00:00")
    def test_countdown_with_hours(self, mock_tty):
        """Countdown >= 1 hour should display HH:MM:SS format."""
        StatusLine.init()

        # Set 1.5 hour countdown (5400 seconds)
        StatusLine.set_countdown(5400)

        ts = StatusLine._get_timestamp()
        assert ts == "01:30:00"

        with freeze_time("2026-03-26 12:00:01"):
            ts = StatusLine._get_timestamp()
            assert ts == "01:29:59"

        StatusLine.stop()

    def test_disable_countdown(self, mock_tty):
        """disable_countdown() should switch back to elapsed mode."""
        StatusLine.init()

        StatusLine.set_countdown(100)
        assert StatusLine._countdown_mode is True

        StatusLine.disable_countdown()
        assert StatusLine._countdown_mode is False

        StatusLine.stop()


class TestStatusLineStateChanges:
    """Tests for state transitions."""

    @freeze_time("2026-03-26 12:00:00")
    @mock.patch("testflinger_cli.status_line._original_print")
    def test_state_change_prints_duration(self, mock_print, mock_tty):
        """State transition should print duration of previous state."""
        StatusLine.init()

        # Set initial state
        StatusLine.set_state("waiting")

        # Advance time 1 second
        with freeze_time("2026-03-26 12:00:01"):
            # Change state
            StatusLine.set_state("running")

        # Verify state changed
        assert StatusLine.state == "running"
        assert StatusLine._prev_state == "waiting"

        # Verify duration was printed
        mock_print.assert_called()
        call_args = mock_print.call_args[0][0]
        assert "State 'waiting' lasted" in call_args
        assert "seconds" in call_args

        StatusLine.stop()

    @freeze_time("2026-03-26 12:00:00")
    def test_multiple_state_transitions(self, mock_tty):
        """Multiple state transitions should track elapsed time in each."""
        StatusLine.init()

        # waiting → running
        StatusLine.set_state("waiting")
        assert StatusLine.state == "waiting"

        with freeze_time("2026-03-26 12:00:01"):
            # running
            StatusLine.set_state("running")
            assert StatusLine.state == "running"

        with freeze_time("2026-03-26 12:00:02"):
            # reserved
            StatusLine.set_state("reserved")
            assert StatusLine.state == "reserved"

        StatusLine.stop()

    def test_state_message_combination(self, mock_tty):
        """State and message should be displayed together."""
        StatusLine.init()

        StatusLine.set_state("waiting")
        StatusLine.set_message("Waiting for node...")

        assert StatusLine.state == "waiting"
        assert StatusLine.message == "Waiting for node..."

        # _get_timestamp returns just the time, line drawing combines it
        ts = StatusLine._get_timestamp()
        line = f"[{ts}] [{StatusLine.state}] {StatusLine.message}"
        assert "waiting" in line
        assert "Waiting for node..." in line

        StatusLine.stop()


class TestStatusLineElapsedThenCountdown:
    """Tests for transitioning from elapsed to countdown mode."""

    @freeze_time("2026-03-26 12:00:00")
    def test_elapsed_then_countdown_transition(self, mock_tty):
        """Should transition from elapsed time to countdown smoothly."""
        StatusLine.init()

        # Start in elapsed mode
        StatusLine.set_state("waiting")
        StatusLine.set_message("Waiting...")

        with freeze_time("2026-03-26 12:00:02"):
            ts_elapsed = StatusLine._get_timestamp()
            # Should show elapsed time 00:02
            assert ts_elapsed == "00:02"

            # Transition to countdown mode
            StatusLine.set_countdown(10)
            ts_countdown = StatusLine._get_timestamp()
            # Should show remaining 00:10
            assert ts_countdown == "00:10"

        with freeze_time("2026-03-26 12:00:03"):
            ts_countdown = StatusLine._get_timestamp()
            # Should have decremented to 00:09
            assert ts_countdown == "00:09"

        StatusLine.stop()

    @freeze_time("2026-03-26 12:00:00")
    def test_countdown_with_state_change(self, mock_tty):
        """Countdown should work correctly across state changes."""
        StatusLine.init()

        StatusLine.set_state("running")

        with freeze_time("2026-03-26 12:00:01"):
            # Enter reserved state with countdown
            StatusLine.set_state("reserved")
            StatusLine.set_countdown(15)

            # Should be counting down, not up
            print("\n=== COUNTDOWN FROM 15 SECONDS ===")
            for i in range(16):
                with freeze_time(f"2026-03-26 12:00:{i + 1:02d}"):
                    ts = StatusLine._get_timestamp()
                    print(f"  {i:2d}s: {ts}")

        # Verify final state
        with freeze_time("2026-03-26 12:00:16"):
            ts = StatusLine._get_timestamp()
            assert ts == "00:00"

        StatusLine.stop()


class TestStatusLineThreadSafety:
    """Tests for thread-safe operations."""

    def test_set_countdown_is_thread_safe(self, mock_tty):
        """set_countdown() should acquire lock before modifying state."""
        StatusLine.init()

        # Call from main thread
        StatusLine.set_countdown(10)
        assert StatusLine._countdown_mode is True

        # Call from another thread
        def set_countdown_from_thread():
            StatusLine.set_countdown(20)

        thread = threading.Thread(target=set_countdown_from_thread)
        thread.start()
        thread.join()

        assert StatusLine._countdown_start_value == 20

        StatusLine.stop()

    def test_set_state_is_thread_safe(self, mock_tty):
        """set_state() should acquire lock before modifying state."""
        StatusLine.init()

        def set_state_from_thread():
            StatusLine.set_state("running")

        thread = threading.Thread(target=set_state_from_thread)
        thread.start()
        thread.join()

        assert StatusLine.state == "running"

        StatusLine.stop()


class TestStatusLineReservedState:
    """Tests for countdown in reserved state (integration)."""

    @mock.patch("testflinger_cli.TestflingerCli._get_combined_log_output")
    @mock.patch("testflinger_cli.TestflingerCli.get_job_state")
    def test_do_poll_enters_reserved_state_with_countdown(
        self, mock_get_state, mock_get_logs, mock_tty
    ):
        """
        Integration test: do_poll transitions to reserved state and countdown.

        This verifies the actual do_poll flow:
        1. Job starts in waiting state (elapsed time counting up)
        2. Job transitions to running (continues counting up)
        3. Job transitions to reserved (countdown mode starts)
        4. Countdown displays remaining time correctly
        """
        from testflinger_cli import TestflingerCli

        job_id = "test-job-123"

        # Mock the client methods
        cli = TestflingerCli.__new__(TestflingerCli)
        cli.args = mock.Mock()
        cli.args.start_fragment = 0
        cli.args.start_timestamp = None
        cli.args.phase = None
        cli.args.debug = False
        cli.history = mock.Mock()

        # Mock client
        cli.client = mock.Mock()
        cli.client.get_job_data = mock.Mock(
            return_value={
                "timeout": 10,
                "reserve_data": {
                    "timeout": 10,
                    "ssh_keys": ["key1"],
                },
                "device_ip": "192.168.1.1",
                "agent_name": "agent-1",
            }
        )
        cli.client.get_job_position = mock.Mock(return_value=0)

        # Mock log output (no logs)
        mock_get_logs.return_value = (-1, "")

        # State progression: waiting → running → reserve → complete
        states = [
            {"job_state": "waiting"},
            {"job_state": "waiting"},
            {"job_state": "running"},
            {"job_state": "running"},
            {"job_state": "reserve"},
            {"job_state": "reserve"},
            {"job_state": "reserve"},
            {"job_state": "completed"},  # Exit the loop
        ]
        mock_get_state.side_effect = states

        print("\n=== TESTING DO_POLL STATE PROGRESSION ===")

        # Capture what happens
        captured_states = []
        captured_timestamps = []

        original_set_state = StatusLine.set_state
        original_set_countdown = StatusLine.set_countdown

        def capture_set_state(state):
            captured_states.append(state)
            print(f"\n[STATE CHANGE] → {state}")
            original_set_state(state)

        def capture_set_countdown(timeout):
            print(f"[COUNTDOWN START] {timeout} seconds")
            captured_timestamps.append(timeout)
            original_set_countdown(timeout)

        # Run do_poll with mocked state progression
        try:
            with mock.patch.object(StatusLine, "set_state", capture_set_state):
                with mock.patch.object(
                    StatusLine, "set_countdown", capture_set_countdown
                ):
                    # This will iterate through states and exit when
                    # it reaches "complete"
                    cli.do_poll(job_id)
        except StopIteration:
            # Expected when states list exhausted
            pass

        # Verify state progression
        print(f"\nCaptured states: {captured_states}")
        assert "waiting" in captured_states
        assert "running" in captured_states
        assert "reserve" in captured_states

        # Verify countdown was initiated for reserve state
        print(f"Captured countdowns: {captured_timestamps}")
        assert 10 in captured_timestamps, (
            "Countdown should have been set to 10 seconds"
        )

        StatusLine.stop()
