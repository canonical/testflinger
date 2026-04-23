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

"""Persistent status line with thread-safe print operations."""

import builtins
import sys
import threading
import time

# Save originals before we override them
_original_print = builtins.print
_original_input = builtins.input


class StatusLine:
    """Persistent status line displayed at the bottom of terminal output.

    A wrapper namespace providing thread-safe print operations with an
    always-visible status line. Runs a daemon timer thread that updates
    the timestamp at configurable intervals.

    All operations are class-level (static methods) to avoid instantiation.
    """

    _print_lock = threading.Lock()
    message = ""
    state = ""
    update_rate = 10.0
    _started = False
    _running = False
    _timer_thread = None
    _original_start_time = None  # Never reset, tracks total elapsed
    _start_time = None  # Reset in countdown mode, tracks display time
    _countdown_mode = False
    _countdown_start_value = 0
    _is_tty = False
    _last_template = ""
    _last_template_state = None
    _prev_state = None
    _state_start_time = None

    @classmethod
    def configure(cls, update_rate=10.0) -> None:
        """Configure update rate before calling start().

        :param update_rate: Hz (updates per second, default 10.0)
        """
        cls.update_rate = update_rate

    @classmethod
    def start(cls):
        """Start the status line timer thread."""
        if cls._running:
            return
        cls._running = True
        now = time.time()
        cls._original_start_time = now  # Capture original start
        cls._start_time = now  # Also set display timer
        cls._timer_thread = threading.Thread(
            target=cls._timer_loop, daemon=True
        )
        cls._timer_thread.start()

    @classmethod
    def stop(cls):
        """Stop the status line timer thread and restore original builtins."""
        cls._running = False
        if cls._timer_thread:
            cls._timer_thread.join(timeout=2.0)
        if cls._started:
            sys.stdout.write("\n")
        sys.stdout.flush()
        builtins.print = _original_print
        builtins.input = _original_input

    @classmethod
    def _timer_loop(cls):
        """Timer thread: update timestamp and redraw at configured rate."""
        if not cls._is_tty:
            return

        while cls._running:
            with cls._print_lock:
                cls.clear()
                cls.draw()
            # Only redraw in TTY environment (no spam in CI/logs)
            time.sleep(1.0 / cls.update_rate)

    @classmethod
    def set_state(cls, state: str) -> None:
        """Update the job state and handle state transitions.

        When state changes, prints elapsed time in previous state.
        Output buffer access is thread-safe via print lock.

        :param state: New job state string
        """
        # When the state changes, track the time
        if cls.state != state:
            if cls._state_start_time and cls.state:
                elapsed = int(time.time() - cls._state_start_time)
                hours = elapsed // 3600
                minutes = (elapsed % 3600) // 60
                seconds = elapsed % 60
                duration_str = f"{minutes} minutes {seconds} seconds"
                if hours > 0:
                    duration_str = f"{hours} hours {duration_str}"
                # Clear status line before printing to avoid mixed output
                with cls._print_lock:
                    cls.clear()
                    _original_print(
                        f"State '{cls.state}' lasted {duration_str}"
                    )
            cls._prev_state = cls.state
            cls.state = state
            cls._state_start_time = time.time()

    @classmethod
    def set_message(cls, template: str, *args, **kwargs) -> None:
        """Update the status line message (output buffer thread-safe).
        Supports string format templates.

        The message will be drawn on the next timer cycle.
        In non-TTY environments, this is a no-op (no status line available).

        :param template: Format string (e.g., "Processing jobs ... {}")
        :param args: Positional arguments for format()
        :param kwargs: Keyword arguments for format()
        """
        if not cls._is_tty:
            return

        message = template.format(*args, **kwargs)
        cls.message = message
        # Capture the status messages with timers to the console on status
        # line (template) change within the same state:
        if (
            cls._last_template
            and template != cls._last_template
            and cls._last_template_state == cls.state
        ):
            with cls._print_lock:
                _original_print(
                    f"[{cls._get_timestamp()}] [{cls.state}] {message}"
                )
        # if we track the last template and what state it was for, we can log
        # meaningful changes while within that state. We are already logging
        # state changes in set_state
        cls._last_template = template
        cls._last_template_state = cls.state

    @classmethod
    def _get_timestamp(cls):
        """Return elapsed/countdown time as MM:SS or HH:MM:SS."""
        if cls._start_time is None:
            return "00:00"

        if cls._countdown_mode:
            # Countdown mode: subtract elapsed from initial value
            elapsed = time.time() - cls._start_time
            remaining = max(0, cls._countdown_start_value - int(elapsed))
            hours = remaining // 3600
            minutes = (remaining % 3600) // 60
            seconds = remaining % 60
            if cls._countdown_start_value >= 3600:
                # Show HH:MM:SS if initial value >= 1 hour
                return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                # Show MM:SS otherwise
                return f"{minutes:02d}:{seconds:02d}"
        else:
            # Elapsed mode: count up from start
            elapsed = int(time.time() - cls._start_time)
            hours = elapsed // 3600
            minutes = (elapsed % 3600) // 60
            seconds = elapsed % 60
            if elapsed >= 3600:
                # Show HH:MM:SS if elapsed time >= 1 hour
                return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                # Show MM:SS otherwise
                return f"{minutes:02d}:{seconds:02d}"

    @classmethod
    def get_elapsed_time(cls):
        """Return elapsed time as (hours, minutes, seconds) tuple.

        Uses _original_start_time to ignore countdown mode resets.
        """
        if cls._original_start_time is None:
            return (0, 0, 0)
        elapsed = int(time.time() - cls._original_start_time)
        hours = elapsed // 3600
        minutes = (elapsed % 3600) // 60
        seconds = elapsed % 60
        return (hours, minutes, seconds)

    @classmethod
    def set_countdown(cls, initial_seconds: int) -> None:
        """Enable countdown mode starting from initial_seconds.

        Sets the countdown flag, initial value, and resets the timer.
        Not all state updates are guarded by locks; timer thread only reads
        these fields at draw time, so minor timing skew is acceptable.

        :param initial_seconds: Countdown duration in seconds
        """
        cls._countdown_mode = True
        cls._countdown_start_value = initial_seconds
        cls._start_time = time.time()

    @classmethod
    def disable_countdown(cls):
        """Disable countdown mode."""
        cls._countdown_mode = False

    @classmethod
    def clear(cls):
        """Clear the status line using ANSI sequences.

        Assumes lock is already held by caller.
        """
        if not cls._is_tty:
            return

        # Move cursor to start of line, clear to end of line
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()

    @classmethod
    def draw(cls):
        """Draw the status line at current cursor position.

        Assumes lock is already held by caller.
        """
        if not cls._is_tty:
            return

        timestamp = cls._get_timestamp()
        line = f"[{timestamp}] [{cls.state}] {cls.message}"
        sys.stdout.write(line)
        sys.stdout.flush()

    @staticmethod
    def print(*args, **kwargs):
        """Thread-safe print wrapper that preserves status line.

        Clears status line before printing, then restores it after.
        """
        with StatusLine._print_lock:
            StatusLine.clear()
            _original_print(*args, **kwargs)
            StatusLine.draw()

    @staticmethod
    def input(prompt=""):
        """Thread-safe input wrapper that preserves status line.

        Clears status line before prompting, restores after user input.
        """
        with StatusLine._print_lock:
            StatusLine.clear()
            result = _original_input(prompt)
            StatusLine.draw()
        return result

    @classmethod
    def init(cls, update_rate: float = 1.0) -> None:
        """Initialize StatusLine: configure, override print and input, start
        timer.

        Call this once at application startup.

        :param update_rate: Hz (updates per second, default 1.0)
        """
        # If not a TTY, init is a no-op (allows normal print in piped output)
        cls._is_tty = sys.stdout.isatty()
        if not cls._is_tty:
            return

        cls._started = True
        cls.configure(update_rate)
        builtins.print = cls.print
        builtins.input = cls.input
        cls.start()
