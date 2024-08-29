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
    "config-branch": "unified-agent-host-charm",
}


@pytest.mark.skip_if_deployed
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


async def test_supervisord_files_written(ops_test: OpsTest):
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
    # check that agent001.conf was written in /etc/supervisor/conf.d/
    expected_contents = (
        "[program:agent001]\n"
        "environment=PYTHONIOENCODING=utf-8\n"
        "user=ubuntu\n"
        "command=/srv/testflinger-venv/bin/testflinger-agent -c /srv/agent-configs/agent/charms/"
        "testflinger-agent-host-charm/tests/integration/data/agent001/"
        "testflinger-agent.conf\n"
    )

    conf_file = "/etc/supervisor/conf.d/agent001.conf"
    unit_name = f"{APP_NAME}/0"
    command = ["exec", "--unit", unit_name, "--", "cat", conf_file]
    returncode, stdout, _ = await ops_test.juju(*command)
    assert returncode == 0
    assert stdout == expected_contents
