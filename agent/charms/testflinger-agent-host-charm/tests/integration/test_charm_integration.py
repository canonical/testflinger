from pathlib import Path

import pytest
from defaults import LOCAL_TESTFLINGER_PATH, VIRTUAL_ENV_PATH
from pytest_operator.plugin import OpsTest

# Root of the charm we need to build is two dirs up
CHARM_PATH = Path(__file__).parent.parent.parent
APP_NAME = "testflinger-agent-host"
TEST_CONFIG_01 = {
    "config-repo": "https://github.com/canonical/testflinger.git",
    "config-dir": "agent/charms/testflinger-agent-host-charm/tests/integration/data/test01",
    "config-branch": "main",
}
TEST_CONFIG_02 = {
    "config-repo": "https://github.com/canonical/testflinger.git",
    "config-dir": "agent/charms/testflinger-agent-host-charm/tests/integration/data/test02",
    "config-branch": "main",
}


@pytest.mark.skip_if_deployed
@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test: OpsTest):
    charm = await ops_test.build_charm(CHARM_PATH)
    app = await ops_test.model.deploy(charm)
    await ops_test.model.applications[APP_NAME].set_config(TEST_CONFIG_01)

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

    # Ensure that Testflinger packages are installed properly
    unit_name = f"{APP_NAME}/0"
    command = [
        "exec",
        "--unit",
        unit_name,
        "--",
        f"{VIRTUAL_ENV_PATH}/bin/pip3",
        "freeze",
    ]
    returncode, stdout, stderr = await ops_test.juju(*command)
    assert returncode == 0, f"{stderr}\n{stdout}"
    for package, path in (
        ("testflinger-common", "common"),
        ("testflinger-agent", "agent"),
        ("testflinger-device-connectors", "device-connectors"),
    ):
        assert f"{package} @ file://{LOCAL_TESTFLINGER_PATH}/{path}" in stdout


async def test_action_update_testflinger_with_branch(ops_test: OpsTest):
    await ops_test.model.wait_for_idle(status="active", timeout=600)
    action = await ops_test.model.units.get(f"{APP_NAME}/0").run_action(
        "update-testflinger",
        branch="main",
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
    await ops_test.model.applications[APP_NAME].set_config(TEST_CONFIG_01)
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
    await ops_test.model.applications[APP_NAME].set_config(TEST_CONFIG_01)
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
        "redirect_stderr=true\n"
        'environment=USER="ubuntu",HOME="/home/ubuntu",'
        "PYTHONIOENCODING=utf-8\n"
        "user=ubuntu\n"
        "command=/srv/testflinger-venv/bin/testflinger-agent -c "
        "/srv/agent-configs/agent/charms/testflinger-agent-host-charm/tests/"
        "integration/data/test01/agent001/testflinger-agent.conf\n"
    )

    conf_file = "/etc/supervisor/conf.d/agent001.conf"
    unit_name = f"{APP_NAME}/0"
    command = ["exec", "--unit", unit_name, "--", "cat", conf_file]
    returncode, stdout, _ = await ops_test.juju(*command)
    assert returncode == 0
    assert stdout == expected_contents


async def test_supervisord_num_agents_running(ops_test: OpsTest):
    # Check that the number of running agents is correct after an update
    await ops_test.model.applications[APP_NAME].set_config(TEST_CONFIG_01)
    action = await ops_test.model.units.get(f"{APP_NAME}/0").run_action(
        "update-configs"
    )
    await action.wait()
    assert action.status == "completed"
    assert (
        ops_test.model.applications[APP_NAME].units[0].workload_status
        == "active"
    )

    unit_name = f"{APP_NAME}/0"
    command = ["exec", "--unit", unit_name, "--", "supervisorctl", "status"]
    returncode, stdout, stderr = await ops_test.juju(*command)
    assert returncode == 0, f"{stderr}\n{stdout}"
    running_agents = [
        line for line in stdout.splitlines() if "RUNNING" in line
    ]
    assert len(running_agents) == 1

    # Update the configs used to one that should launch two agents
    await ops_test.model.applications[APP_NAME].set_config(TEST_CONFIG_02)
    action = await ops_test.model.units.get(f"{APP_NAME}/0").run_action(
        "update-configs"
    )
    await action.wait()
    assert action.status == "completed"
    assert (
        ops_test.model.applications[APP_NAME].units[0].workload_status
        == "active"
    )

    # Check that the number of running agents is now 2
    unit_name = f"{APP_NAME}/0"
    command = ["exec", "--unit", unit_name, "--", "supervisorctl", "status"]
    returncode, stdout, stderr = await ops_test.juju(*command)
    assert returncode == 0, f"{stderr}\n{stdout}"
    running_agents = [
        line for line in stdout.splitlines() if "RUNNING" in line
    ]
    assert len(running_agents) == 2
