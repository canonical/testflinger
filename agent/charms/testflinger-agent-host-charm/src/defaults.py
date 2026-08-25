# Copyright 2024 Canonical
# See LICENSE file for licensing details.
"""Default values for the Testflinger Agent Host charm."""

AGENT_CONFIGS_PATH = "/srv/agent-configs"
DEFAULT_TESTFLINGER_REPO = "https://github.com/canonical/testflinger.git"
DEFAULT_BRANCH = "main"
LOCAL_TESTFLINGER_PATH = "/srv/testflinger"
VIRTUAL_ENV_PATH = "/srv/testflinger-venv"
DEFAULT_TOKEN_PATH = "/var/lib/testflinger-agent/refresh_token"  # noqa S105
UV_BIN_PATH = "/root/.local/bin/uv"
