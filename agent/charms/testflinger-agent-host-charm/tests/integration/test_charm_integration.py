# Copyright 2026 Canonical
# See LICENSE file for licensing details.
"""Integration tests for the charm."""

import json
import os
import platform
from pathlib import Path

import jubilant
import pytest
import yaml
from conftest import create_mock_token

from defaults import (
    LOCAL_TESTFLINGER_PATH,
    VIRTUAL_ENV_PATH,
)

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
# Build and deploy natively; the runner's OS version is not the charm's base.
NATIVE_ARCH = {"x86_64": "amd64", "aarch64": "arm64"}.get(
    platform.machine(), platform.machine()
)
TEST_BASE = os.environ.get(
    "TEST_BASE", platform.freedesktop_os_release()["VERSION_ID"]
)


@pytest.mark.juju_setup
def test_deploy(charm_path: Path, juju: jubilant.Juju):
    """Deploy the charm under test."""
    juju.deploy(
        charm_path.resolve(),
        app=APP_NAME,
        constraints={"arch": NATIVE_ARCH},
        base=f"ubuntu@{TEST_BASE}",
    )
    juju.config(APP_NAME, TEST_CONFIG_01)
    # Include cold image provisioning and snap/package installation on SD
    # storage. The charm should then block due to missing credentials.
    juju.wait(jubilant.all_blocked, timeout=60 * 20)

    # Create mock token to skip authentication
    create_mock_token(juju, APP_NAME)
    # Trigger update-status to re-evaluate authentication
    charm_dir = f"/var/lib/juju/agents/unit-{APP_NAME}-0/charm"
    juju.exec(
        "bash",
        "-c",
        f"cd {charm_dir} && JUJU_DISPATCH_PATH=hooks/update-status ./dispatch",
        unit=f"{APP_NAME}/0",
    )
    juju.wait(jubilant.all_active)


def test_guest_platform(juju: jubilant.Juju):
    """The guest must match the selected base and native architecture."""
    architecture = juju.exec(
        "dpkg", "--print-architecture", unit=f"{APP_NAME}/0"
    )
    assert architecture.return_code == 0
    assert architecture.stdout.strip() == NATIVE_ARCH

    os_release = juju.exec("cat", "/etc/os-release", unit=f"{APP_NAME}/0")
    assert os_release.return_code == 0
    release = dict(
        line.split("=", 1)
        for line in os_release.stdout.splitlines()
        if "=" in line
    )
    assert release["ID"].strip('"') == "ubuntu"
    assert release["VERSION_ID"].strip('"') == TEST_BASE


def test_update_testflinger_action(juju: jubilant.Juju):
    """Test the update-testflinger action."""
    action = juju.run(f"{APP_NAME}/0", "update-testflinger")
    assert action.status == "completed"
    assert action.return_code == 0

    packages = (
        ("testflinger-common", "common"),
        ("testflinger-agent", "agent"),
        ("testflinger-device-connectors", "device-connectors"),
    )
    # pip freeze may render a local editable install as a Git URL. Check
    # PEP 610 metadata instead, retaining the local-source provenance check.
    metadata = juju.exec(
        f"{VIRTUAL_ENV_PATH}/bin/python3",
        "-c",
        "import json, sys; from importlib.metadata import distribution; "
        "print(json.dumps({name: json.loads("
        "distribution(name).read_text('direct_url.json') or 'null') "
        "for name in sys.argv[1:]}))",
        *(package for package, _ in packages),
        unit=f"{APP_NAME}/0",
    )
    assert metadata.return_code == 0
    installed_sources = json.loads(metadata.stdout)
    for package, path in packages:
        source = installed_sources[package]
        assert isinstance(source, dict), f"Missing source metadata: {package}"
        expected_url = (Path(LOCAL_TESTFLINGER_PATH) / path).as_uri()
        assert source.get("url") == expected_url, (package, source)


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
    assert conf_file.stdout.strip() == expected_contents.strip()


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


@pytest.mark.juju_teardown
def test_destroy(juju: jubilant.Juju):
    """Tear down the charm under test."""
    juju.remove_application(APP_NAME)
