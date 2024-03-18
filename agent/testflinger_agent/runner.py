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
import shlex
import signal
import subprocess
import threading
import time

from typing import Callable, Optional, List

logger = logging.getLogger(__name__)


class CommandRunner:
    def __init__(self, cwd: Optional[str], env: Optional[dict]):
        self.output_handlers: List[Callable] = []
        self.stop_condition_checkers: List[Callable] = []
        self.process: Optional[subprocess.Popen] = None
        self.cwd = cwd
        self.env = os.environ.copy()
        if env:
            self.env.update(
                {k: str(v) for k, v in env.items() if isinstance(v, str)}
            )

    def register_output_handler(self, handler: Callable[[str], None]):
        self.output_handlers.append(handler)

    def post_output(self, data: str):
        for handler in self.output_handlers:
            handler(data)

    def register_stop_condition_checker(
        self, checker: Callable[[], Optional[str]]
    ):
        self.stop_condition_checkers.append(checker)

    def check_stop_conditions(self) -> bool:
        for checker in self.stop_condition_checkers:
            output = checker()
            if output:
                # This shouldn't happen, but makes mypy happy
                assert self.process is not None
                self.post_output(output)
                return True
        return False

    def check_output(self):
        raw_output = self.process.stdout.read()
        if not raw_output:
            return

        output = raw_output.decode(sys.stdout.encoding, errors="replace")
        self.post_output(output)

    def run_command_thread(self, cmd: str):
        self.process = subprocess.Popen(
            shlex.split(cmd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=self.cwd,
            env=self.env,
        )
        # Ensure that the output doesn't get buffered on our end
        if self.process.stdout is not None:
            set_nonblock(self.process.stdout.fileno())
        self.process.wait()

    def cleanup(self):
        if self.process is not None:
            self.process.kill()

    def run(self, cmd: str) -> int:

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

            if self.check_stop_conditions():
                self.cleanup()
                break

            self.check_output()
        # Check for any final output before exiting

        run_cmd_thread.join()
        self.check_output()

        signal.signal(signal.SIGTERM, signal.SIG_DFL)

        return self.process.returncode


def set_nonblock(fd: int):
    """Set the specified fd to nonblocking output

    :param fd:
        File descriptor that should be set to nonblocking mode
    """

    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
