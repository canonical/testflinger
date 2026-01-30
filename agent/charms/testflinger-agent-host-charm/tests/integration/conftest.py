import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import jubilant
import pytest
from defaults import DEFAULT_TOKEN_PATH

logger = logging.getLogger(__name__)


def create_mock_token(juju: jubilant.Juju, app_name: str):
    """Create a mock token file so authentication is skipped.

    This creates a valid token file with a recent obtained_at timestamp.
    """
    token_data = json.dumps(
        {
            "refresh_token": "mock-token",
            "obtained_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    token_dir = str(Path(DEFAULT_TOKEN_PATH).parent)
    juju.exec("mkdir", "-p", token_dir, unit=f"{app_name}/0")
    juju.exec(
        "bash",
        "-c",
        f"echo '{token_data}' > {DEFAULT_TOKEN_PATH}",
        unit=f"{app_name}/0",
    )


@pytest.fixture(scope="module")
def juju(request: pytest.FixtureRequest):
    """Create temporary Juju model for running tests."""
    with jubilant.temp_model() as juju:
        juju.wait_timeout = 600
        yield juju

        if request.session.testsfailed:
            logger.info("Collecting Juju logs...")
            time.sleep(0.5)  # Wait for Juju to process logs.
            log = juju.debug_log(limit=1000)
            print(log, end="", file=sys.stderr)


@pytest.fixture(scope="session")
def charm_path():
    """Return the path of the charm under test."""
    if "CHARM_PATH" in os.environ:
        charm_path = Path(os.environ["CHARM_PATH"])
        if not charm_path.exists():
            raise FileNotFoundError(f"Charm does not exist: {charm_path}")
        return charm_path
    charm_paths = list(Path(".").glob("*.charm"))
    if not charm_paths:
        raise FileNotFoundError("No .charm file in current directory")
    if len(charm_paths) > 1:
        path_list = ", ".join(str(p) for p in charm_paths)
        raise ValueError(
            f"More than one .charm file in current directory: {path_list}"
        )
    return charm_paths[0]
