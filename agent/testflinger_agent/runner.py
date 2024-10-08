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

import logging
import os
import fcntl
import sys
import signal
import subprocess
import threading
import time

from collections import defaultdict
from typing import Callable, List, Optional, Tuple, Type

from testflinger_common.enums import TestEvent

logger = logging.getLogger(__name__)

StopConditionType = Callable[[], Optional[str]]


class RunnerEvent:
    """
    Runner events that can be subscribed to.
    """

    @classmethod
    def event_name(cls):
        """
        Return a unique event name (the fully qualified class name) to use
        as a key in dictionaries.
        """
        return f"{cls.__module__}.{cls.__qualname__}"


# Any event handler expects to be called with the event as an argument
RunnerEventHandlerType = Callable[[RunnerEvent], None]


class OutputEvent(RunnerEvent):
    """
    A type of event corresponding to the generation of output during a test.
    The output is stored in the corresponding `output` attribute.
    """

    def __init__(self, output: str):
        self.output = output


class CommandRunner:
    """
    Run a command and handle events and stop conditions.

    There are also events that can be subscribed to for notifications.
    """

    def __init__(self, cwd: Optional[str], env: Optional[dict]):
        self.stop_condition_checkers: List[StopConditionType] = []
        self.process: Optional[subprocess.Popen] = None
        self.cwd = cwd
        self.env = os.environ.copy()
        # a mapping of event names to lists of registered event handlers
        self.events = defaultdict(list)
        if env:
            self.env.update(
                {k: str(v) for k, v in env.items() if isinstance(v, str)}
            )

    def subscribe_event(
        self, event_cls: Type[RunnerEvent], handler: RunnerEventHandlerType
    ):
        """Set a callback for an event that we want to be notified of"""
        self.events[event_cls.event_name()].append(handler)

    def post_event(self, event: RunnerEvent):
        """Post an event for subscribers to be notified of"""
        for handler in self.events[type(event).event_name()]:
            handler(event)

    def register_stop_condition_checker(self, checker: StopConditionType):
        self.stop_condition_checkers.append(checker)

    def check_stop_conditions(self) -> Tuple[Optional[TestEvent], str]:
        """
        Check stop conditions and return the reason if any are met. Otherwise,
        return an empty string if none are met
        """
        for checker in self.stop_condition_checkers:
            event, detail = checker()
            if event is not None:
                return event, detail
        return None, ""

    def check_and_post_output(self):
        raw_output = self.process.stdout.read()
        if not raw_output:
            return
        self.post_event(
            OutputEvent(
                raw_output.decode(sys.stdout.encoding, errors="replace")
            )
        )

    def run_command_thread(self, cmd: str):
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=self.cwd,
            env=self.env,
            shell=True,
        )
        # Ensure that the output doesn't get buffered on our end
        if self.process.stdout is not None:
            set_nonblock(self.process.stdout.fileno())
        self.process.wait()

    def cleanup(self):
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        if self.process is not None:
            self.process.kill()

    def run(self, cmd: str) -> Tuple[int, Optional[TestEvent], str]:
        # Ensure that the process is None before starting
        self.process = None
        stop_event = None
        stop_reason = ""

        signal.signal(signal.SIGTERM, lambda signum, frame: self.cleanup())

        run_cmd_thread = threading.Thread(
            target=self.run_command_thread, args=(cmd,)
        )
        run_cmd_thread.start()

        # Make sure to wait until the process actually starts
        while self.process is None:
            time.sleep(1)

        while self.process.poll() is None:
            time.sleep(10)

            stop_event, stop_reason = self.check_stop_conditions()
            if stop_event is not None:
                self.post_event(OutputEvent(f"\n{stop_reason}\n"))
                self.cleanup()
                break

            self.check_and_post_output()

        # Check for any final output before exiting
        run_cmd_thread.join()
        self.check_and_post_output()
        self.cleanup()
        if stop_reason == "":
            stop_reason = get_stop_reason(self.process.returncode, "")

        return self.process.returncode, stop_event, stop_reason


def get_stop_reason(returncode: int, stop_reason: str) -> str:
    """
    Try to give some reason for the job stopping based on what we know.
    """
    if returncode == 0:
        return "Normal exit"
    return f"Unknown error rc={returncode}"


def set_nonblock(fd: int):
    """Set the specified fd to nonblocking output

    :param fd:
        File descriptor that should be set to nonblocking mode
    """

    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
