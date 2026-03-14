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

import os
import signal
import subprocess
import time

import pytest


@pytest.mark.timeout(60)
def test_restart_signal_handler(tmp_path):
    # Ensure the agent restarts when it receives the restart signal
    agent_config_file = tmp_path / "testflinger-agent.conf"
    agent_config_file.write_text(
        "agent_id: test-agent-1\n"
        "server_address: http://127.0.0.1:5000\n"
        "polling_interval: 5\n"
        "job_queues:\n"
        "  - test\n"
    )

    agent_process = subprocess.Popen(  # noqa: S603
        ["testflinger-agent", "-c", str(agent_config_file)],  # noqa: S607
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    time.sleep(5)
    try:
        os.kill(agent_process.pid, signal.SIGUSR1)

        # Use communicate with timeout
        try:
            stdout, stderr = agent_process.communicate(timeout=6)
            assert "Marked agent for restart" in stderr
            assert agent_process.returncode == 1
        except subprocess.TimeoutExpired:
            # Process didn't terminate in time, force kill and get output
            agent_process.kill()
            stdout, stderr = agent_process.communicate()
            # Still check for the restart message
            assert "Marked agent for restart" in stderr
    except Exception as e:
        pytest.fail(f"Test failed with exception: {e}")
    finally:
        if agent_process.poll() is None:
            agent_process.kill()
