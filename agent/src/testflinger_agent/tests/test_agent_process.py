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

import signal
import subprocess
import time
import os


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

    agent_process = subprocess.Popen(
        [
            "testflinger-agent",
            "-c",
            str(agent_config_file),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        # Wait for the agent to start
        time.sleep(1)
        os.kill(agent_process.pid, signal.SIGUSR1)
        time.sleep(1)

        assert os.path.exists("/tmp/TESTFLINGER-DEVICE-RESTART-test-agent-1")
        assert (
            "Marked agent for restart" in agent_process.stderr.read().decode()
        )

        # Ensure the agent process is terminated
        assert agent_process.wait(timeout=2) == 1
    finally:
        agent_process.kill()
