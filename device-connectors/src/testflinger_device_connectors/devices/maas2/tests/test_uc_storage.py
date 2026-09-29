"""Ubuntu Core post-deployment storage tests (no real disks are touched)."""

import json
import subprocess
from unittest.mock import patch

import pytest

from testflinger_device_connectors.devices import ProvisioningError
from testflinger_device_connectors.devices.maas2 import Maas2
from testflinger_device_connectors.devices.maas2.uc_storage import (
    apply_data_disk,
    plan_data_disks,
)


def test_plan_handles_multiple_physical_data_disks():
    machine = {"boot_disk": {"id": 1}}
    devices = [
        {"id": 1, "type": "physical", "serial": "BOOT"},
        {
            "id": 2,
            "type": "physical",
            "serial": "DATA-A",
            "id_path": "/dev/disk/by-id/ata-a",
            "partitions": [
                {
                    "size": 100,
                    "filesystem": {"fstype": "ext4", "label": "data-a"},
                }
            ],
        },
        {
            "id": 3,
            "type": "physical",
            "serial": "DATA-B",
            "id_path": "/dev/disk/by-id/nvme-b",
            "partitions": [
                {
                    "size": 200,
                    "filesystem": {"fstype": "ext4", "label": "data-b"},
                }
            ],
        },
    ]
    assert [item["serial"] for item in plan_data_disks(machine, devices)] == [
        "DATA-A",
        "DATA-B",
    ]


def test_plan_rejects_unsupported_layout_before_writing():
    machine = {"boot_disk": {"id": 1}}
    devices = [
        {"id": 1, "type": "physical", "serial": "BOOT"},
        {
            "id": 2,
            "type": "physical",
            "serial": "DATA",
            "id_path": "/dev/disk/by-id/ata-d",
            "partitions": [{"filesystem": {"fstype": "xfs"}}],
        },
    ]
    with pytest.raises(ProvisioningError, match="Unsupported"):
        plan_data_disks(machine, devices)


def test_plan_ignores_maas_partition_size_for_uc():
    machine = {"boot_disk": {"id": 1}}
    devices = [
        {"id": 1, "type": "physical", "serial": "BOOT"},
        {
            "id": 2,
            "type": "physical",
            "size": 2_000_000_000,
            "serial": "DATA",
            "id_path": "/dev/disk/by-id/ata-d",
            "partitions": [
                {"size": 1_000_000_000, "filesystem": {"fstype": "ext4"}}
            ],
        },
    ]
    assert plan_data_disks(machine, devices) == [
        {"serial": "DATA", "path": "/dev/disk/by-id/ata-d", "label": ""}
    ]


def test_plan_accepts_maas_default_full_disk_partition_overhead():
    machine = {"boot_disk": {"id": 986}}
    devices = [
        {"id": 986, "type": "physical", "serial": "BOOT"},
        {
            "id": 987,
            "type": "physical",
            "size": 256060514304,
            "available_size": 0,
            "serial": "DATA",
            "id_path": "/dev/disk/by-id/nvme-data",
            "partitions": [
                {
                    "size": 256053870592,
                    "filesystem": {"fstype": "ext4", "label": "data"},
                }
            ],
        },
    ]
    assert plan_data_disks(machine, devices) == [
        {
            "serial": "DATA",
            "path": "/dev/disk/by-id/nvme-data",
            "label": "data",
        }
    ]


def test_plan_ignores_maas_available_size_for_uc():
    machine = {"boot_disk": {"id": 1}}
    devices = [
        {"id": 1, "type": "physical", "serial": "BOOT"},
        {
            "id": 2,
            "type": "physical",
            "size": 100_000_000,
            "available_size": 1_000_000,
            "serial": "DATA",
            "id_path": "/dev/disk/by-id/data",
            "partitions": [
                {"size": 99_000_000, "filesystem": {"fstype": "ext4"}}
            ],
        },
    ]
    assert plan_data_disks(machine, devices) == [
        {"serial": "DATA", "path": "/dev/disk/by-id/data", "label": ""}
    ]


def test_plan_rejects_data_disk_with_boot_serial():
    machine = {"boot_disk": {"id": 1}}
    devices = [
        {"id": 1, "type": "physical", "serial": "SAME"},
        {
            "id": 2,
            "type": "physical",
            "serial": "SAME",
            "id_path": "/dev/disk/by-id/data",
            "partitions": [{"filesystem": {"fstype": "ext4"}}],
        },
    ]
    with pytest.raises(ProvisioningError, match="boot disk serial"):
        plan_data_disks(machine, devices)


def test_plan_rejects_multiple_partitions():
    machine = {"boot_disk": {"id": 1}}
    devices = [
        {"id": 1, "type": "physical", "serial": "BOOT"},
        {
            "id": 2,
            "type": "physical",
            "serial": "DATA",
            "id_path": "/dev/disk/by-id/ata-d",
            "partitions": [
                {"filesystem": {"fstype": "ext4"}},
                {"filesystem": {"fstype": "ext4"}},
            ],
        },
    ]
    with pytest.raises(ProvisioningError, match="Unsupported"):
        plan_data_disks(machine, devices)


def test_plan_rejects_boot_disk_missing_from_inventory():
    with pytest.raises(ProvisioningError, match="boot disk"):
        plan_data_disks(
            {"boot_disk": {"id": 1}}, [{"id": 2, "type": "physical"}]
        )


def test_plan_skips_unconfigured_disks_and_rejects_missing_boot_disk():
    with pytest.raises(ProvisioningError, match="boot disk"):
        plan_data_disks({}, [])
    assert (
        plan_data_disks(
            {"boot_disk": {"id": 1}},
            [
                {"id": 1, "type": "physical", "serial": "BOOT"},
                {
                    "id": 2,
                    "type": "physical",
                    "serial": "UNUSED",
                    "partitions": [],
                },
            ],
        )
        == []
    )


def test_apply_data_disk_creates_only_verified_blank_disk():
    disk = {
        "serial": "DATA",
        "path": "/dev/disk/by-id/ata-data",
        "label": "data",
    }
    before = {
        "blockdevices": [
            {
                "path": "/dev/sdb",
                "type": "disk",
                "serial": "DATA",
                "size": 2_000_000_000,
                "mountpoints": [None],
            }
        ]
    }
    after = {
        "blockdevices": [
            {
                "path": "/dev/sdb",
                "type": "disk",
                "serial": "DATA",
                "size": 2000000000,
                "children": [
                    {
                        "path": "/dev/sdb1",
                        "type": "part",
                        "fstype": None,
                        "size": 1999000000,
                    }
                ],
            }
        ]
    }
    verified = {
        "blockdevices": [
            {
                "path": "/dev/sdb",
                "type": "disk",
                "serial": "DATA",
                "size": 2000000000,
                "children": [
                    {
                        "path": "/dev/sdb1",
                        "type": "part",
                        "fstype": "ext4",
                        "label": "data",
                        "size": 1999000000,
                    }
                ],
            }
        ]
    }
    states = iter([before, after, verified])
    commands = []

    def ssh(command, input_data=None):
        commands.append((command, input_data))
        if "lsblk" in command:
            state = next(states)
            if " -T " not in command:
                # PATH without --tree makes partitions sibling entries.
                root = state["blockdevices"][0].copy()
                children = root.pop("children", [])
                state = {"blockdevices": [root, *children]}
            return subprocess.CompletedProcess([], 0, json.dumps(state))
        return subprocess.CompletedProcess([], 0, "")

    apply_data_disk(ssh, disk)
    assert any("sfdisk" in cmd and data for cmd, data in commands)
    assert any("mkfs.ext4" in cmd for cmd, _ in commands)
    assert commands[-1][0].startswith("sudo -n lsblk -T -J")


def test_apply_data_disk_verifies_ext4_when_lsblk_is_temporarily_stale():
    """Probe the superblock without trusting udev's cache."""
    disk = {
        "serial": "DATA",
        "path": "/dev/disk/by-id/ata-data",
        "label": "data",
    }

    def state(fstype=None, label=None, partition=False):
        root = {"path": "/dev/sdb", "type": "disk", "serial": "DATA"}
        if partition:
            root["children"] = [
                {
                    "path": "/dev/sdb1",
                    "type": "part",
                    "fstype": fstype,
                    "label": label,
                }
            ]
        return json.dumps({"blockdevices": [root]})

    scans = iter([state(), state(partition=True), state(partition=True)])
    commands = []

    def ssh(command, input_data=None):
        commands.append(command)
        if "lsblk" in command:
            return subprocess.CompletedProcess([], 0, next(scans))
        if "blkid -p" in command:
            return subprocess.CompletedProcess(
                [], 0, "TYPE=ext4\nLABEL=data\n"
            )
        return subprocess.CompletedProcess([], 0, "")

    apply_data_disk(ssh, disk)
    assert sum("sfdisk" in command for command in commands) == 1
    assert sum("mkfs.ext4" in command for command in commands) == 1
    assert any(
        "blkid -p" in command and "/dev/sdb1" in command
        for command in commands
    )


def test_apply_data_disk_retries_transient_superblock_probe():
    disk = {
        "serial": "DATA",
        "path": "/dev/disk/by-id/ata-data",
        "label": "data",
    }
    bare = {"path": "/dev/sdb", "type": "disk", "serial": "DATA"}
    partitioned = {
        **bare,
        "children": [
            {
                "path": "/dev/sdb1",
                "type": "part",
                "fstype": None,
                "label": None,
            }
        ],
    }
    scans = iter([bare, partitioned, partitioned, partitioned])
    probes = iter(["", "TYPE=ext4\nLABEL=data\n"])
    commands = []

    def ssh(command, input_data=None):
        commands.append(command)
        if "lsblk" in command:
            return subprocess.CompletedProcess(
                [], 0, json.dumps({"blockdevices": [next(scans)]})
            )
        if "blkid -p" in command:
            return subprocess.CompletedProcess([], 0, next(probes))
        return subprocess.CompletedProcess([], 0, "")

    with patch("time.sleep") as sleep:
        apply_data_disk(ssh, disk)
    sleep.assert_called_once_with(1)
    assert sum("mkfs.ext4" in command for command in commands) == 1
    assert sum("sfdisk" in command for command in commands) == 1


def test_apply_data_disk_rejects_wrong_superblock_without_rewriting():
    disk = {
        "serial": "DATA",
        "path": "/dev/disk/by-id/ata-data",
        "label": "data",
    }
    bare = {"path": "/dev/sdb", "type": "disk", "serial": "DATA"}
    partitioned = {
        **bare,
        "children": [
            {
                "path": "/dev/sdb1",
                "type": "part",
                "fstype": None,
                "label": None,
            }
        ],
    }
    scans = iter(
        [bare, partitioned, partitioned, partitioned, partitioned, partitioned]
    )
    commands = []

    def ssh(command, input_data=None):
        commands.append(command)
        if "lsblk" in command:
            return subprocess.CompletedProcess(
                [], 0, json.dumps({"blockdevices": [next(scans)]})
            )
        if "blkid -p" in command:
            return subprocess.CompletedProcess(
                [], 0, "TYPE=xfs\nLABEL=wrong\n"
            )
        return subprocess.CompletedProcess([], 0, "")

    with (
        patch("time.sleep") as sleep,
        pytest.raises(ProvisioningError, match="blkid=.*xfs.*wrong") as error,
    ):
        apply_data_disk(ssh, disk)
    assert "disk=DATA" in str(error.value)
    assert sleep.call_count == 2
    assert sum("mkfs.ext4" in command for command in commands) == 1
    assert sum("sfdisk" in command for command in commands) == 1


def test_apply_data_disk_refuses_foreign_disk_and_existing_partition():
    disk = {
        "serial": "DATA",
        "path": "/dev/disk/by-id/ata-data",
        "label": "data",
    }
    for actual in [
        {"path": "/dev/sdb", "type": "disk", "serial": "OTHER"},
        {
            "path": "/dev/sdb",
            "type": "disk",
            "serial": "DATA",
            "children": [
                {"path": "/dev/sdb1", "type": "part", "fstype": "xfs"}
            ],
        },
    ]:
        commands = []

        def make_ssh(expected, calls):
            def ssh(command, input_data=None):
                calls.append(command)
                return subprocess.CompletedProcess(
                    [], 0, json.dumps({"blockdevices": [expected]})
                )

            return ssh

        with pytest.raises(ProvisioningError):
            apply_data_disk(make_ssh(actual, commands), disk)
        assert not any(
            "sfdisk" in entry or "mkfs.ext4" in entry for entry in commands
        )


def test_apply_data_disk_accepts_existing_matching_ext4_without_formatting():
    disk = {
        "serial": "DATA",
        "path": "/dev/disk/by-id/ata-data",
        "label": "data",
    }
    state = {
        "blockdevices": [
            {
                "path": "/dev/sdb",
                "type": "disk",
                "serial": "DATA",
                "children": [
                    {
                        "path": "/dev/sdb1",
                        "type": "part",
                        "fstype": "ext4",
                        "label": "data",
                        "mountpoints": [None],
                    }
                ],
            }
        ]
    }
    commands = []

    def ssh(command, input_data=None):
        commands.append(command)
        return subprocess.CompletedProcess([], 0, json.dumps(state))

    apply_data_disk(ssh, disk)
    assert len(commands) == 1


def test_wait_for_refresh_skips_pending_reboot(mock_config_file):
    job_file = mock_config_file.parent / "job.json"
    job_file.write_text(json.dumps({}))
    device = Maas2(mock_config_file, job_file)
    outputs = iter(
        [
            "boot-one",
            "ID Status Spawn Ready Summary\n1 Wait now - Auto-refresh\n",
            "boot-one",
            "boot-two",
            "ID Status Spawn Ready Summary\n1 Done now now Auto-refresh\n",
            "boot-two",
        ]
    )

    def ssh(command):
        output = "" if "seed.loaded" in command else next(outputs)
        return subprocess.CompletedProcess([], 0, output)

    with (
        patch.object(device, "run_uc_ssh", side_effect=ssh),
        patch("time.sleep") as sleep,
    ):
        device.wait_for_uc_refresh_idle()
    sleep.assert_called_once_with(10)


def test_uc_without_data_disks_does_not_hold_refresh(mock_config_file):
    job_file = mock_config_file.parent / "job.json"
    job_file.write_text(json.dumps({}))
    device = Maas2(mock_config_file, job_file)
    responses = iter(
        [
            {"boot_disk": {"id": 1}},
            [{"id": 1, "type": "physical", "serial": "BOOT"}],
        ]
    )

    def maas_result(command):
        return subprocess.CompletedProcess(
            command, 0, json.dumps(next(responses)).encode()
        )

    with (
        patch.object(
            device, "run_maas_cmd_with_retry", side_effect=maas_result
        ),
        patch.object(device, "run_uc_ssh") as ssh,
    ):
        device.prepare_ubuntu_core_storage()
    ssh.assert_not_called()


def test_uc_holds_refresh_before_applying_all_data_disks(mock_config_file):
    job_file = mock_config_file.parent / "job.json"
    job_file.write_text(json.dumps({}))
    device = Maas2(mock_config_file, job_file)
    machine = {"boot_disk": {"id": 1}}
    disks = [{"id": 1, "type": "physical", "serial": "BOOT"}] + [
        {
            "id": n,
            "type": "physical",
            "serial": f"DATA-{n}",
            "id_path": f"/dev/disk/by-id/data-{n}",
            "partitions": [
                {"filesystem": {"fstype": "ext4", "label": f"data-{n}"}}
            ],
        }
        for n in (2, 3)
    ]
    events = []

    def maas_result(command):
        result = machine if command[2:4] == ["machine", "read"] else disks
        return subprocess.CompletedProcess(
            command, 0, json.dumps(result).encode()
        )

    def ssh_result(command, **kwargs):
        events.append(command)
        return subprocess.CompletedProcess(command, 0, b"")

    with (
        patch.object(
            device, "run_maas_cmd_with_retry", side_effect=maas_result
        ),
        patch.object(device, "run_uc_ssh", side_effect=ssh_result),
        patch.object(device, "wait_for_uc_refresh_idle"),
        patch.object(
            device,
            "apply_uc_disk",
            side_effect=lambda disk: events.append(disk["serial"]),
        ),
    ):
        device.prepare_ubuntu_core_storage()

    assert events == [
        "sudo -n snap refresh --hold=2h",
        "DATA-2",
        "DATA-3",
        "sudo -n snap refresh --unhold",
    ]


def test_uc_rejects_unsupported_layout_before_holding_refresh(
    mock_config_file,
):
    job_file = mock_config_file.parent / "job.json"
    job_file.write_text(json.dumps({}))
    device = Maas2(mock_config_file, job_file)
    responses = iter(
        [
            {"boot_disk": {"id": 1}},
            [
                {"id": 1, "type": "physical", "serial": "BOOT"},
                {
                    "id": 2,
                    "type": "physical",
                    "serial": "DATA",
                    "id_path": "/dev/disk/by-id/ata-d",
                    "partitions": [{"filesystem": {"fstype": "xfs"}}],
                },
            ],
        ]
    )
    commands = []

    def maas_result(command):
        return subprocess.CompletedProcess(
            command, 0, json.dumps(next(responses)).encode()
        )

    def ssh(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess([], 0, "")

    with (
        patch.object(
            device, "run_maas_cmd_with_retry", side_effect=maas_result
        ),
        patch.object(device, "run_uc_ssh", side_effect=ssh),
        patch.object(device, "apply_uc_disk") as apply,
        pytest.raises(ProvisioningError, match="Unsupported"),
    ):
        device.prepare_ubuntu_core_storage()
    apply.assert_not_called()
    assert commands == []


def test_uc_hold_failure_never_touches_storage(mock_config_file):
    job_file = mock_config_file.parent / "job.json"
    job_file.write_text(json.dumps({}))
    device = Maas2(mock_config_file, job_file)
    with (
        patch.object(
            device,
            "run_maas_cmd_with_retry",
            side_effect=[
                subprocess.CompletedProcess([], 0, b'{"boot_disk":{"id":1}}'),
                subprocess.CompletedProcess(
                    [],
                    0,
                    json.dumps(
                        [
                            {"id": 1, "type": "physical", "serial": "BOOT"},
                            {
                                "id": 2,
                                "type": "physical",
                                "serial": "DATA",
                                "id_path": "/dev/disk/by-id/ata-d",
                                "partitions": [
                                    {"filesystem": {"fstype": "ext4"}}
                                ],
                            },
                        ]
                    ).encode(),
                ),
            ],
        ),
        patch.object(
            device, "run_uc_ssh", side_effect=ProvisioningError("hold failed")
        ),
        patch.object(device, "apply_uc_disk") as apply,
        pytest.raises(ProvisioningError, match="hold failed"),
    ):
        device.prepare_ubuntu_core_storage()
    apply.assert_not_called()


def test_uc_unholds_refresh_after_disk_error(mock_config_file):
    job_file = mock_config_file.parent / "job.json"
    job_file.write_text(json.dumps({}))
    device = Maas2(mock_config_file, job_file)
    commands = []

    def ssh(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess([], 0, "")

    with (
        patch.object(
            device,
            "run_maas_cmd_with_retry",
            side_effect=[
                subprocess.CompletedProcess([], 0, b'{"boot_disk":{"id":1}}'),
                subprocess.CompletedProcess(
                    [],
                    0,
                    json.dumps(
                        [
                            {"id": 1, "type": "physical", "serial": "BOOT"},
                            {
                                "id": 2,
                                "type": "physical",
                                "serial": "DATA",
                                "id_path": "/dev/disk/by-id/ata-d",
                                "partitions": [
                                    {"filesystem": {"fstype": "ext4"}}
                                ],
                            },
                        ]
                    ).encode(),
                ),
            ],
        ),
        patch.object(device, "run_uc_ssh", side_effect=ssh),
        patch.object(device, "wait_for_uc_refresh_idle"),
        patch.object(
            device,
            "apply_uc_disk",
            side_effect=ProvisioningError("disk unsafe"),
        ),
        pytest.raises(ProvisioningError, match="disk unsafe"),
    ):
        device.prepare_ubuntu_core_storage()
    assert commands == [
        "sudo -n snap refresh --hold=2h",
        "sudo -n snap refresh --unhold",
    ]


def test_uc_only_calls_post_deployment_storage(mock_config_file):
    job_file = mock_config_file.parent / "job.json"
    job_file.write_text(json.dumps({}))
    device = Maas2(mock_config_file, job_file)
    with (
        patch.object(device, "recover"),
        patch.object(device, "set_flat_storage_layout"),
        patch.object(device, "format_non_os_disks"),
        patch.object(device, "get_current_installation_id", return_value=None),
        patch.object(device, "run_maas_cmd_with_retry") as run_maas,
        patch.object(device, "node_status", return_value="Deployed"),
        patch.object(device, "node_addresses", return_value=["10.10.10.10"]),
        patch.object(device, "check_test_image_booted", return_value=True),
        patch.object(device, "prepare_ubuntu_core_storage") as prepare,
        patch("time.sleep"),
    ):
        run_maas.return_value.stdout = b'{"osystem": "ubuntu"}'
        device.deploy_node(distro="noble")
        prepare.assert_not_called()
        device.deploy_node(distro="ubuntu-core/core24-latest")
        prepare.assert_called_once_with()


def test_bare_core24_series_dispatches_uc_storage(mock_config_file):
    job_file = mock_config_file.parent / "job.json"
    job_file.write_text(json.dumps({}))
    device = Maas2(mock_config_file, job_file)

    def maas_response(cmd):
        if cmd[2:4] == ["machine", "read"]:
            return subprocess.CompletedProcess(
                cmd, 0, stdout=b'{"osystem": "ubuntu-core"}'
            )
        return subprocess.CompletedProcess(cmd, 0, stdout=b"{}")

    with (
        patch.object(device, "recover"),
        patch.object(device, "set_flat_storage_layout"),
        patch.object(device, "format_non_os_disks"),
        patch.object(device, "get_current_installation_id", return_value=None),
        patch.object(
            device, "run_maas_cmd_with_retry", side_effect=maas_response
        ),
        patch.object(device, "node_status", return_value="Deployed"),
        patch.object(device, "node_addresses", return_value=["10.10.10.10"]),
        patch.object(device, "check_test_image_booted", return_value=True),
        patch.object(device, "prepare_ubuntu_core_storage") as prepare,
        patch("time.sleep"),
    ):
        device.deploy_node(distro="core24-latest")
    prepare.assert_called_once_with()
