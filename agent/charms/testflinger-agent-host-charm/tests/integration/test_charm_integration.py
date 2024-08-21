from pathlib import Path
from unittest.mock import patch
import pytest
from pytest_operator.plugin import OpsTest

# Root of the charm we need to build is two dirs up
CHARM_PATH = Path(__file__).parent.parent.parent
APP_NAME = "testflinger-agent-host"
TEST_CONFIG = {
    "config-repo": "https://github.com/canonical/testflinger.git",
    "config-dir": "agent/charms/testflinger-agent-host-charm/tests/integration/data",
    "config-branch": "update-configs-action",
}


@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test: OpsTest):
    charm = await ops_test.build_charm(CHARM_PATH)
    app = await ops_test.model.deploy(charm)
    await ops_test.model.applications[APP_NAME].set_config(TEST_CONFIG)

    await ops_test.model.wait_for_idle(status="active", timeout=600)
    assert app.status == "active"


async def test_action_update_testflinger(ops_test: OpsTest):
    await ops_test.model.wait_for_idle(status="active", timeout=600)
    action = await ops_test.model.units.get(f"{APP_NAME}/0").run_action(
        "update-testflinger"
    )
    await action.wait()
    assert action.status == "completed"
    assert action.results["return-code"] == 0


async def test_action_update_configs(ops_test: OpsTest):
    await ops_test.model.wait_for_idle(status="active", timeout=600)

    # First, un-set the config-repo to trigger BlockedStatus
    bad_config = {"config-repo": ""}
    await ops_test.model.applications[APP_NAME].set_config(bad_config)
    action = await ops_test.model.units.get(f"{APP_NAME}/0").run_action(
        "update-configs"
    )
    await action.wait()
    assert action.status == "completed"
    assert (
        ops_test.model.applications[APP_NAME].units[0].workload_status
        == "blocked"
    )

    # Go back to the good config and make sure we get back to ActiveStatus
    await ops_test.model.applications[APP_NAME].set_config(TEST_CONFIG)
    action = await ops_test.model.units.get(f"{APP_NAME}/0").run_action(
        "update-configs"
    )
    await action.wait()
    assert action.status == "completed"
    assert (
        ops_test.model.applications[APP_NAME].units[0].workload_status
        == "active"
    )
