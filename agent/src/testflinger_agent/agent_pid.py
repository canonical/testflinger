# Copyright (C) 2026 Canonical
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

"""PID management module for the Testflinger agent."""

import atexit
import logging
import os
import signal
from pathlib import Path

logger = logging.getLogger(__name__)


def write(pid_file: Path) -> None:
    """Write the current process PID to the specified file.

    :param pid_file: Path to the PID file to write.
    """
    try:
        pid_file.write_text(str(os.getpid()))
    except OSError as err:
        logger.error("Failed to write PID file %s: %s", pid_file, err)
        raise

    atexit.register(_cleanup, pid_file)


def _safe_unlink(pid_file: Path) -> None:
    """Remove the PID file, logging any error without raising.

    :param pid_file: Path to the PID file to remove.
    """
    try:
        pid_file.unlink(missing_ok=True)
    except OSError as err:
        logger.error("Failed to remove PID file %s: %s", pid_file, err)


def _cleanup(pid_file: Path) -> None:
    """Remove the PID file on process exit.

    :param pid_file: Path to the PID file to remove.
    """
    try:
        if pid_file.exists() and pid_file.read_text().strip() == str(
            os.getpid()
        ):
            _safe_unlink(pid_file)
    except OSError as err:
        logger.error("Failed to check PID file %s: %s", pid_file, err)
        return


def terminate_stale(pid_file: Path, config_path: str) -> None:
    """Terminate a stale agent process if one exists for this agent.

    :param pid_file: Path to the PID file.
    :param config_path: Path to agent config path
    """
    if not pid_file.exists():
        return

    # Verify the process is alive and confirms it matches this agent config
    try:
        stale_pid = int(pid_file.read_text().strip())
        cmdline = (
            Path(f"/proc/{stale_pid}/cmdline")
            .read_bytes()
            .decode(errors="replace")
            .replace("\0", " ")
            .strip()
        )
    except (OSError, ValueError):
        # If PID file is malformed, remove the PID file in agent config_path
        _safe_unlink(pid_file)
        return

    # If stale PID was recycled for an unrelated process, remove only PID file
    if "testflinger-agent" not in cmdline or config_path not in cmdline:
        logger.warning(
            "PID %d does not match this agent — not terminating it",
            stale_pid,
        )
        _safe_unlink(pid_file)
        return

    logger.warning("Terminating orphaned agent process (PID %d)", stale_pid)
    try:
        os.kill(stale_pid, signal.SIGKILL)
    except ProcessLookupError:
        # Process is already terminated, ignore
        pass
