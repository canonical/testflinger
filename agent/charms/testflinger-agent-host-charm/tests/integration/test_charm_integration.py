from pathlib import Path

import jubilant
import yaml
from defaults import LOCAL_TESTFLINGER_PATH, VIRTUAL_ENV_PATH

TEST_CONFIG_01 = {
    "config-repo": "https://github.com/canonical/testflinger.git",
    "config-dir": "agent/charms/testflinger-agent-host-charm/tests/integration/data/test01",  # noqa: E501
    "config-branch": "main",
}
TEST_CONFIG_02 = {
    "config-repo": "https://github.com/canonical/testflinger.git",
    "config-dir": "agent/charms/testflinger-agent-host-charm/tests/integration/data/test02",  # noqa: E501
    "config-branch": "main",
}
SUPERVISOR_CONF_FILE = "/etc/supervisor/conf.d/agent001.conf"


METADATA = yaml.safe_load(Path("charmcraft.yaml").read_text(encoding="utf-8"))
APP_NAME = METADATA["name"]


def test_deploy(charm_path: Path, juju: jubilant.Juju):
    """Deploy the charm under test."""
    juju.deploy(charm_path.resolve(), app=APP_NAME)
    juju.config(APP_NAME, TEST_CONFIG_01)
    juju.wait(jubilant.all_active)


def test_update_testflinger_action(juju: jubilant.Juju):
    """Test the update-testflinger action."""
    action = juju.run(f"{APP_NAME}/0", "update-testflinger")
    assert action.status == "completed"
    assert action.return_code == 0

    # Ensure that Testflinger packages are installed properly
    pip_freeze = juju.exec(
        f"{VIRTUAL_ENV_PATH}/bin/pip3", "freeze", unit=f"{APP_NAME}/0"
    )
    assert pip_freeze.return_code == 0

    for package, path in (
        ("testflinger-common", "common"),
        ("testflinger-agent", "agent"),
        ("testflinger-device-connectors", "device-connectors"),
    ):
        assert (
            f"{package} @ file://{LOCAL_TESTFLINGER_PATH}/{path}"
            in pip_freeze.stdout
        )


def test_update_testflinger_action_with_branch(juju: jubilant.Juju):
    """Test the update-testflinger action with branch parameter."""
    action = juju.run(
        f"{APP_NAME}/0",
        "update-testflinger",
        {"branch": "main"},
    )
    assert action.status == "completed"
    assert action.return_code == 0


def test_update_configs_action(juju: jubilant.Juju):
    """Test events triggered by update-configs action."""
    # First unset the config-repo to trigger BlockedStatus
    juju.config(APP_NAME, {"config-repo": ""})
    action = juju.run(f"{APP_NAME}/0", "update-configs")
    assert action.status == "completed"
    juju.wait(jubilant.all_blocked)

    # Go back to the good config and make sure we get back to ActiveStatus
    juju.config(APP_NAME, TEST_CONFIG_01)
    action = juju.run(f"{APP_NAME}/0", "update-configs")
    assert action.status == "completed"
    juju.wait(jubilant.all_active)


def test_supervisord_files_updated(juju: jubilant.Juju):
    """Test that supervisord config files are updated after update-configs."""
    juju.config(APP_NAME, TEST_CONFIG_01)
    action = juju.run(f"{APP_NAME}/0", "update-configs")
    assert action.status == "completed"

    # check that agent001.conf was written in /etc/supervisor/conf.d/
    expected_contents = (
        "[program:agent001]\n"
        "startsecs=0\n"
        "redirect_stderr=true\n"
        'environment=USER="ubuntu",HOME="/home/ubuntu",'
        "PYTHONIOENCODING=utf-8\n"
        "user=ubuntu\n"
        "command=/srv/testflinger-venv/bin/testflinger-agent -c "
        "/srv/agent-configs/agent/charms/testflinger-agent-host-charm/tests/"
        "integration/data/test01/agent001/testflinger-agent.conf -p 8000\n"
    )
    conf_file = juju.exec("cat", SUPERVISOR_CONF_FILE, unit=f"{APP_NAME}/0")
    assert conf_file.return_code == 0
    assert conf_file.stdout == expected_contents


def test_supervisord_agent_running(juju: jubilant.Juju):
    """Test that supervisord is running the agent after update-configs."""
    juju.config(APP_NAME, TEST_CONFIG_01)
    action = juju.run(f"{APP_NAME}/0", "update-configs")
    assert action.status == "completed"

    # check that agent001 is RUNNING in supervisord
    supervisor_status = juju.exec(
        "supervisorctl", "status", unit=f"{APP_NAME}/0"
    )
    assert supervisor_status.return_code == 0
    running_agents = [
        line
        for line in supervisor_status.stdout.splitlines()
        if "agent001" in line and "RUNNING" in line
    ]
    assert len(running_agents) == 1

    # Update the configs used to one that should launch two agents
    juju.config(APP_NAME, TEST_CONFIG_02)
    action = juju.run(f"{APP_NAME}/0", "update-configs")
    assert action.status == "completed"

    # Check that the number of running agents is now 2
    supervisor_status = juju.exec(
        "supervisorctl", "status", unit=f"{APP_NAME}/0"
    )
    assert supervisor_status.return_code == 0
    running_agents = [
        line
        for line in supervisor_status.stdout.splitlines()
        if "RUNNING" in line
    ]
    assert len(running_agents) == 2
