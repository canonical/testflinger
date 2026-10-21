# Copyright (C) 2022 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
"""Integration test fixtures for testing against a running server.

Uses the testflinger CLI v2 client for full end-to-end testing.
"""

import json
import logging
import os
import sys
import time
from pathlib import Path

import pytest

logger = logging.getLogger(__name__)

# Add cli module to path so we can import testflinger_cli
CLI_PATH = Path(__file__).parent.parent.parent / "cli"
sys.path.insert(0, str(CLI_PATH))

# Add server devel modules to path for sample_users
SERVER_DEVEL_PATH = Path(__file__).parent.parent.parent / "server" / "devel"
sys.path.insert(0, str(SERVER_DEVEL_PATH))

from sample_users import SAMPLE_CLIENTS
from testflinger_cli.client import Client
from testflinger_cli.auth import TestflingerCliAuth


# Find admin client from sample_users
_admin_client = next(
    (c for c in SAMPLE_CLIENTS if c.get("role") == "admin"), None
)

# Use testflinger-admin if available, otherwise fall back to sample_users admin
TESTFLINGER_ADMIN_ID = "testflinger-admin"
TESTFLINGER_ADMIN_SECRET = "testflinger"


@pytest.fixture(scope="session")
def server_url() -> str:
    """Get the server URL from environment or use default.

    Defaults to http://localhost:5000 but can be overridden by setting
    TESTFLINGER_SERVER environment variable.

    Example:
        export TESTFLINGER_SERVER=http://192.168.4.201:5000
    """
    url = os.environ.get("TESTFLINGER_SERVER", "http://localhost:5000")
    logger.info(f"Using server URL: {url}")

    # Verify server is accessible
    max_retries = 30
    retry_count = 0
    while retry_count < max_retries:
        try:
            import requests

            response = requests.get(f"{url}/", timeout=1)
            if response.status_code in [200, 404]:
                logger.info(f"Server at {url} is accessible")
                return url
        except Exception:
            pass
        retry_count += 1
        time.sleep(0.5)

    raise RuntimeError(
        f"Server at {url} is not accessible after {max_retries} retries"
    )


@pytest.fixture
def test_agent_name() -> str:
    """Return the test agent name (default: test_agent)."""
    return os.environ.get("TEST_AGENT_NAME", "test_agent")


@pytest.fixture
def test_queue_name() -> str:
    """Return the test queue name."""
    return "test-queue"


@pytest.fixture
def cli_client(server_url):
    """Provide a CLI client fixture using testflinger v2 CLI.

    Uses the actual TestflingerClient from the CLI with v2 API support.
    """

    class CLIWrapper:
        """Wrapper around TestflingerClient for test convenience."""

        def __init__(self, base_url: str):
            self.base_url = base_url
            # Create auth manager with admin credentials
            self.auth = TestflingerCliAuth(
                server_url=base_url,
                client_id=TESTFLINGER_ADMIN_ID,
                secret_key=TESTFLINGER_ADMIN_SECRET,
            )
            # Create the actual CLI client (server URL, then auth manager)
            self.client = Client(base_url, self.auth)

        def get_agent(self, agent_name: str) -> dict | None:
            """Get agent data using v2 API.

            Returns the agent document with nested mode/state/commanded_mode
            or None if not found.
            """
            try:
                agent_data = self.client.get_agent_data(agent_name)
                logger.info(
                    f"Got agent {agent_name}: "
                    f"{json.dumps(agent_data, indent=2, default=str)}"
                )
                return agent_data
            except Exception as e:
                logger.error(f"Failed to get agent {agent_name}: {e}")
                return None

        def list_agents(self) -> list | None:
            """List all agents using v2 API."""
            try:
                agents = self.client.get_all_agents()
                logger.info(f"Got {len(agents)} agents")
                return agents
            except Exception as e:
                logger.error(f"Failed to list agents: {e}")
                return None

        def set_agent_mode(
            self, agent_name: str, mode: str, comment: str = ""
        ) -> bool:
            """Set agent commanded_mode using v2 API (admin operation).

            Returns True if successful.
            """
            try:
                self.client.set_agent_status(agent_name, mode, comment)
                logger.info(f"Set {agent_name} mode to {mode}")
                return True
            except Exception as e:
                logger.error(f"Failed to set agent mode: {e}")
                return False

    return CLIWrapper(server_url)
