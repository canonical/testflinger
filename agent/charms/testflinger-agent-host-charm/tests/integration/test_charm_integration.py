from pathlib import Path
import pytest
from pytest_operator.plugin import OpsTest

# Root of the charm we need to build is two dirs up
CHARM_PATH = Path(__file__).parent.parent.parent
APP_NAME = "testflinger-agent-host"


@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test: OpsTest):
    charm = await ops_test.build_charm(CHARM_PATH)
    app = await ops_test.model.deploy(charm)

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
