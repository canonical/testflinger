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


def test_run_uc_ssh_passes_input_and_returns_output(mock_config_file):
    job_file = mock_config_file.parent / "job.json"
    job_file.write_text("{}")
    device = Maas2(mock_config_file, job_file)
    result = subprocess.CompletedProcess([], 0, "partitioned", "")
    with patch("subprocess.run", return_value=result) as run:
        assert device.run_uc_ssh("sudo -n sfdisk", "layout\n") is result
    args, kwargs = run.call_args
    assert args[0][-2:] == [
        f"ubuntu@{device.config['device_ip']}",
        "sudo -n sfdisk",
    ]
    assert kwargs["input"] == "layout\n"
    assert kwargs["timeout"] == 60
    assert kwargs["check"] is False


def test_apply_uc_disk_delegates_to_data_disk_setup(mock_config_file):
    job_file = mock_config_file.parent / "job.json"
    job_file.write_text("{}")
    device = Maas2(mock_config_file, job_file)
    disk = {"serial": "DATA", "path": "/dev/disk/by-id/ata-data"}
    with patch(
        "testflinger_device_connectors.devices.maas2.maas2.apply_data_disk"
    ) as apply:
        device.apply_uc_disk(disk)
    apply.assert_called_once_with(device.run_uc_ssh, disk)


def test_run_uc_ssh_reports_nonzero_exit_and_timeout(mock_config_file):
    job_file = mock_config_file.parent / "job.json"
    job_file.write_text("{}")
    device = Maas2(mock_config_file, job_file)
    with patch(
        "subprocess.run",
        return_value=subprocess.CompletedProcess(
            [], 1, "", "permission denied"
        ),
    ):
        with pytest.raises(ProvisioningError, match="permission denied"):
            device.run_uc_ssh("sudo -n lsblk")
    with patch(
        "subprocess.run",
        side_effect=subprocess.TimeoutExpired(["ssh"], 60),
    ):
        with pytest.raises(ProvisioningError, match="timed out"):
            device.run_uc_ssh("sudo -n lsblk")


def test_run_uc_ssh_reports_process_launch_error(mock_config_file):
    job_file = mock_config_file.parent / "job.json"
    job_file.write_text("{}")
    device = Maas2(mock_config_file, job_file)
    with patch("subprocess.run", side_effect=OSError("ssh unavailable")):
        with pytest.raises(ProvisioningError, match="ssh unavailable"):
            device.run_uc_ssh("sudo -n lsblk")


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


@pytest.mark.parametrize(
    ("machine_change", "data_change", "extra_data", "message"),
    [
        ({"serial": "OTHER"}, {}, None, "boot disk serial"),
        ({}, {"serial": None}, None, "serial and a stable"),
        ({}, {"id_path": None}, None, "serial and a stable"),
        ({}, {"id_path": "/dev/sdb"}, None, "serial and a stable"),
        (
            {},
            {"id_path": "/dev/disk/by-id/ata-boot"},
            None,
            "boot disk serial or path",
        ),
        ({}, {"bootable": True}, None, "bootable or mounted"),
        ({}, {"mount_point": "/data"}, None, "bootable or mounted"),
        ({}, {"label": "x" * 17}, None, "ext4 label"),
        ({}, {"label": "bad/name"}, None, "ext4 label"),
        ({}, {"label": "bad\nname"}, None, "ext4 label"),
        ({}, {"label": "bad\rname"}, None, "ext4 label"),
        ({}, {"filesystem": {"fstype": "ext4"}}, None, "one partition"),
        ({}, {}, {}, "Duplicate data disk identity"),
        (
            {},
            {},
            {"serial": "DATA", "id_path": "/dev/disk/by-id/ata-other"},
            "Duplicate data disk identity",
        ),
    ],
)
def test_plan_rejects_unsafe_disk_identity_or_layout(
    machine_change, data_change, extra_data, message
):
    machine = {"boot_disk": {"id": 1, **machine_change}}
    boot = {
        "id": 1,
        "type": "physical",
        "serial": "BOOT",
        "id_path": "/dev/disk/by-id/ata-boot",
    }
    data = {
        "id": 2,
        "type": "physical",
        "serial": "DATA",
        "id_path": "/dev/disk/by-id/ata-data",
        "partitions": [{"filesystem": {"fstype": "ext4"}}],
    }
    if "bootable" in data_change:
        data["partitions"][0]["bootable"] = data_change["bootable"]
    if "mount_point" in data_change:
        data["partitions"][0]["filesystem"]["mount_point"] = data_change[
            "mount_point"
        ]
    if "label" in data_change:
        data["partitions"][0]["filesystem"]["label"] = data_change["label"]
    data.update(
        {
            key: value
            for key, value in data_change.items()
            if key not in {"bootable", "mount_point", "label"}
        }
    )
    devices = [boot, data]
    if extra_data is not None:
        devices.append({**data, "id": 3, "serial": "OTHER", **extra_data})
    with pytest.raises(ProvisioningError, match=message):
        plan_data_disks(machine, devices)


@pytest.mark.parametrize(
    ("lsblk_result", "wipe_signature", "message"),
    [
        ("{", "", "Invalid lsblk response"),
        ("{}", "", "Invalid lsblk response"),
        ({"blockdevices": []}, "", "not a single physical disk"),
        (
            {"blockdevices": [{"type": "part", "serial": "DATA"}]},
            "",
            "not a single physical disk",
        ),
        (
            {"blockdevices": [{"type": "disk", "serial": "DATA"}] * 2},
            "",
            "not a single physical disk",
        ),
        (
            {"blockdevices": [{"type": "disk", "serial": "OTHER"}]},
            "",
            "serial does not match",
        ),
        (
            {
                "blockdevices": [
                    {
                        "type": "disk",
                        "serial": "DATA",
                        "children": [{"label": "ubuntu-data"}],
                    }
                ]
            },
            "",
            "system disk",
        ),
        (
            {
                "blockdevices": [
                    {"type": "disk", "serial": "DATA", "fstype": "ext4"}
                ]
            },
            "",
            "already formatted or mounted",
        ),
        (
            {
                "blockdevices": [
                    {
                        "type": "disk",
                        "serial": "DATA",
                        "mountpoints": ["/data"],
                    }
                ]
            },
            "",
            "already formatted or mounted",
        ),
        (
            {"blockdevices": [{"type": "disk", "serial": "DATA"}]},
            "gpt signature",
            "partition table or signature",
        ),
    ],
)
def test_apply_data_disk_rejects_unsafe_disk_before_writes(
    lsblk_result, wipe_signature, message
):
    disk = {
        "serial": "DATA",
        "path": "/dev/disk/by-id/ata-data",
        "label": "data",
    }
    commands = []

    def ssh(command, input_data=None):
        commands.append(command)
        output = wipe_signature if "wipefs --no-act" in command else ""
        if "lsblk" in command:
            output = (
                lsblk_result
                if isinstance(lsblk_result, str)
                else json.dumps(lsblk_result)
            )
        return subprocess.CompletedProcess([], 0, output)

    with pytest.raises(ProvisioningError, match=message):
        apply_data_disk(ssh, disk)
    assert not any(
        "sfdisk" in command or "mkfs" in command for command in commands
    )


@pytest.mark.parametrize("label", ["data", ""])
def test_apply_data_disk_creates_only_verified_blank_disk(label):
    disk = {
        "serial": "DATA",
        "path": "/dev/disk/by-id/ata-data",
        "label": label,
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
                        "label": label,
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
            return subprocess.CompletedProcess([], 0, json.dumps(state))
        return subprocess.CompletedProcess([], 0, "")

    apply_data_disk(ssh, disk)
    assert any("sfdisk" in cmd and data for cmd, data in commands)
    assert any("mkfs.ext4" in cmd for cmd, _ in commands)
    assert all(
        (" -L " in cmd) == bool(label)
        for cmd, _ in commands
        if "mkfs.ext4" in cmd
    )
    assert commands[-1][0].startswith("sudo -n lsblk -T -J")


@pytest.mark.parametrize(
    ("partition", "message"),
    [
        (None, "partition was not created"),
        ({"path": "/dev/sdb1", "type": "disk"}, "partition was not created"),
        (
            {"path": "/dev/sdb1", "type": "part", "fstype": "ext4"},
            "partition was not created",
        ),
        ({"path": "", "type": "part"}, "no block device path"),
        ({"path": "sdb1", "type": "part"}, "no block device path"),
    ],
)
def test_apply_data_disk_rejects_bad_partition_after_sfdisk(
    partition, message
):
    disk = {
        "serial": "DATA",
        "path": "/dev/disk/by-id/ata-data",
        "label": "data",
    }
    bare = {"path": "/dev/sdb", "type": "disk", "serial": "DATA"}
    partitioned = {
        **bare,
        "children": [partition] if partition is not None else [],
    }
    scans = iter([bare, partitioned])
    commands = []

    def ssh(command, input_data=None):
        commands.append(command)
        if "lsblk" in command:
            return subprocess.CompletedProcess(
                [], 0, json.dumps({"blockdevices": [next(scans)]})
            )
        return subprocess.CompletedProcess([], 0, "")

    with pytest.raises(ProvisioningError, match=message):
        apply_data_disk(ssh, disk)
    assert sum("sfdisk" in command for command in commands) == 1
    assert not any("mkfs.ext4" in command for command in commands)


def test_apply_data_disk_fails_if_layout_changes_during_verification():
    disk = {
        "serial": "DATA",
        "path": "/dev/disk/by-id/ata-data",
        "label": "data",
    }
    bare = {"path": "/dev/sdb", "type": "disk", "serial": "DATA"}
    partition = {"path": "/dev/sdb1", "type": "part"}
    scans = iter(
        [
            bare,
            {**bare, "children": [partition]},
            {**bare, "children": [{**partition, "path": "/dev/sdb2"}]},
        ]
    )
    commands = []

    def ssh(command, input_data=None):
        commands.append(command)
        if "lsblk" in command:
            return subprocess.CompletedProcess(
                [], 0, json.dumps({"blockdevices": [next(scans)]})
            )
        return subprocess.CompletedProcess([], 0, "")

    with pytest.raises(ProvisioningError, match="verification failed"):
        apply_data_disk(ssh, disk)
    assert sum("sfdisk" in command for command in commands) == 1
    assert sum("mkfs.ext4" in command for command in commands) == 1
    assert not any("blkid" in command for command in commands)


def test_apply_data_disk_does_not_rewrite_after_transient_blkid_failure():
    disk = {
        "serial": "DATA",
        "path": "/dev/disk/by-id/ata-data",
        "label": "data",
    }
    bare = {"path": "/dev/sdb", "type": "disk", "serial": "DATA"}
    partitioned = {
        **bare,
        "children": [{"path": "/dev/sdb1", "type": "part"}],
    }
    scans = iter([bare, partitioned, partitioned, partitioned])
    commands = []
    probes = iter(
        [
            ProvisioningError("probe temporarily unavailable"),
            "TYPE=ext4\nLABEL=data\n",
        ]
    )

    def ssh(command, input_data=None):
        commands.append(command)
        if "lsblk" in command:
            return subprocess.CompletedProcess(
                [], 0, json.dumps({"blockdevices": [next(scans)]})
            )
        if "blkid -p" in command:
            output = next(probes)
            if isinstance(output, Exception):
                raise output
            return subprocess.CompletedProcess([], 0, output)
        return subprocess.CompletedProcess([], 0, "")

    with patch("time.sleep") as sleep:
        apply_data_disk(ssh, disk)
    sleep.assert_called_once_with(1)
    assert sum("sfdisk" in command for command in commands) == 1
    assert sum("mkfs.ext4" in command for command in commands) == 1
    assert sum("blkid -p" in command for command in commands) == 2


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


def test_wait_for_refresh_reconnects_after_ssh_failure(mock_config_file):
    job_file = mock_config_file.parent / "job.json"
    job_file.write_text("{}")
    device = Maas2(mock_config_file, job_file)
    responses = [
        ProvisioningError("rebooting"),
        subprocess.CompletedProcess([], 0, "boot-id"),
        subprocess.CompletedProcess([], 0, ""),
        subprocess.CompletedProcess([], 0, "ID Status\n1 Done\n"),
        subprocess.CompletedProcess([], 0, "boot-id"),
    ]
    with (
        patch.object(device, "run_uc_ssh", side_effect=responses),
        patch("time.sleep") as sleep,
    ):
        device.wait_for_uc_refresh_idle()
    sleep.assert_called_once_with(10)


def test_wait_for_refresh_times_out_after_repeated_ssh_failure(
    mock_config_file,
):
    job_file = mock_config_file.parent / "job.json"
    job_file.write_text("{}")
    device = Maas2(mock_config_file, job_file)
    with (
        patch.object(
            device, "run_uc_ssh", side_effect=ProvisioningError("offline")
        ),
        patch("time.monotonic", side_effect=[0, 0, 600]),
        patch("time.sleep") as sleep,
        pytest.raises(ProvisioningError, match="did not settle"),
    ):
        device.wait_for_uc_refresh_idle()
    sleep.assert_called_once_with(10)


def test_uc_preserves_existing_refresh_hold(mock_config_file):
    job_file = mock_config_file.parent / "job.json"
    job_file.write_text("{}")
    device = Maas2(mock_config_file, job_file)
    commands = []

    def ssh(command):
        commands.append(command)
        return subprocess.CompletedProcess(
            [], 0, '{"refresh":{"hold":"forever"}}', ""
        )

    with (
        patch.object(
            device,
            "run_maas_cmd_with_retry",
            return_value=subprocess.CompletedProcess([], 0, b"{}"),
        ),
        patch(
            "testflinger_device_connectors.devices.maas2.maas2.plan_data_disks",
            return_value=[{"serial": "DATA"}],
        ),
        patch.object(device, "run_uc_ssh", side_effect=ssh),
        patch.object(device, "wait_for_uc_refresh_idle"),
        patch.object(device, "apply_uc_disk") as apply,
    ):
        device.prepare_ubuntu_core_storage()
    assert commands == ["sudo -n snap get -d system"]
    apply.assert_called_once_with({"serial": "DATA"})


@pytest.mark.parametrize(
    ("hold", "allowed"),
    [
        ("2099-01-01T00:00:00Z", True),
        ("2000-01-01T00:00:00Z", False),
        ("2099-01-01T00:00:00", False),
        ("invalid", False),
    ],
)
def test_uc_existing_refresh_hold_must_be_valid_and_long_enough(
    mock_config_file, hold, allowed
):
    job_file = mock_config_file.parent / "job.json"
    job_file.write_text("{}")
    device = Maas2(mock_config_file, job_file)
    commands = []

    def ssh(command):
        commands.append(command)
        return subprocess.CompletedProcess(
            [], 0, json.dumps({"refresh": {"hold": hold}}), ""
        )

    with (
        patch.object(
            device,
            "run_maas_cmd_with_retry",
            return_value=subprocess.CompletedProcess([], 0, b"{}"),
        ),
        patch(
            "testflinger_device_connectors.devices.maas2.maas2.plan_data_disks",
            return_value=[{"serial": "DATA"}],
        ),
        patch.object(device, "run_uc_ssh", side_effect=ssh),
        patch.object(device, "wait_for_uc_refresh_idle"),
        patch.object(device, "apply_uc_disk") as apply,
    ):
        if allowed:
            device.prepare_ubuntu_core_storage()
        else:
            with pytest.raises(ProvisioningError, match="refresh hold"):
                device.prepare_ubuntu_core_storage()
    assert commands == ["sudo -n snap get -d system"]
    assert apply.call_count == int(allowed)


def test_uc_rejects_unreadable_refresh_configuration(mock_config_file):
    job_file = mock_config_file.parent / "job.json"
    job_file.write_text("{}")
    device = Maas2(mock_config_file, job_file)
    with (
        patch.object(
            device,
            "run_maas_cmd_with_retry",
            return_value=subprocess.CompletedProcess([], 0, b"{}"),
        ),
        patch(
            "testflinger_device_connectors.devices.maas2.maas2.plan_data_disks",
            return_value=[{"serial": "DATA"}],
        ),
        patch.object(
            device,
            "run_uc_ssh",
            return_value=subprocess.CompletedProcess([], 0, "invalid-json"),
        ) as ssh,
        patch.object(device, "apply_uc_disk") as apply,
        pytest.raises(ProvisioningError, match="Unable to read"),
    ):
        device.prepare_ubuntu_core_storage()
    ssh.assert_called_once_with("sudo -n snap get -d system")
    apply.assert_not_called()


def test_uc_ambiguous_hold_timeout_keeps_bounded_hold(mock_config_file):
    job_file = mock_config_file.parent / "job.json"
    job_file.write_text("{}")
    device = Maas2(mock_config_file, job_file)
    commands = []

    def ssh(command):
        commands.append(command)
        if command == "sudo -n snap get -d system":
            return subprocess.CompletedProcess([], 0, "{}", "")
        raise ProvisioningError("UC SSH command timed out: hold")

    with (
        patch.object(
            device,
            "run_maas_cmd_with_retry",
            return_value=subprocess.CompletedProcess([], 0, b"{}"),
        ),
        patch(
            "testflinger_device_connectors.devices.maas2.maas2.plan_data_disks",
            return_value=[{"serial": "DATA"}],
        ),
        patch.object(device, "run_uc_ssh", side_effect=ssh),
        patch.object(device, "apply_uc_disk") as apply,
        pytest.raises(ProvisioningError, match="timed out"),
    ):
        device.prepare_ubuntu_core_storage()
    assert commands == [
        "sudo -n snap get -d system",
        "sudo -n snap refresh --hold=2h",
    ]
    apply.assert_not_called()


def test_uc_warns_when_its_own_hold_cannot_be_removed(
    mock_config_file, caplog
):
    job_file = mock_config_file.parent / "job.json"
    job_file.write_text("{}")
    device = Maas2(mock_config_file, job_file)
    commands = []

    def ssh(command):
        commands.append(command)
        if command == "sudo -n snap get -d system":
            return subprocess.CompletedProcess([], 0, "{}", "")
        if command == "sudo -n snap refresh --unhold":
            raise ProvisioningError("connection lost")
        return subprocess.CompletedProcess([], 0, "", "")

    with (
        patch.object(
            device,
            "run_maas_cmd_with_retry",
            return_value=subprocess.CompletedProcess([], 0, b"{}"),
        ),
        patch(
            "testflinger_device_connectors.devices.maas2.maas2.plan_data_disks",
            return_value=[{"serial": "DATA"}],
        ),
        patch.object(device, "run_uc_ssh", side_effect=ssh),
        patch.object(device, "wait_for_uc_refresh_idle"),
        patch.object(device, "apply_uc_disk") as apply,
    ):
        device.prepare_ubuntu_core_storage()
    apply.assert_called_once()
    assert commands == [
        "sudo -n snap get -d system",
        "sudo -n snap refresh --hold=2h",
        "sudo -n snap refresh --unhold",
    ]
    assert "Could not remove UC refresh hold" in caplog.text


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
        output = "{}" if command == "sudo -n snap get -d system" else ""
        return subprocess.CompletedProcess(command, 0, output)

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
        "sudo -n snap get -d system",
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

    def maas_result(command):
        return subprocess.CompletedProcess(
            command, 0, json.dumps(next(responses)).encode()
        )

    with (
        patch.object(
            device, "run_maas_cmd_with_retry", side_effect=maas_result
        ),
        patch.object(device, "run_uc_ssh") as ssh,
        patch.object(device, "apply_uc_disk") as apply,
        pytest.raises(ProvisioningError, match="Unsupported"),
    ):
        device.prepare_ubuntu_core_storage()
    apply.assert_not_called()
    ssh.assert_not_called()


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
            device,
            "run_uc_ssh",
            side_effect=[
                subprocess.CompletedProcess([], 0, "{}"),
                ProvisioningError("hold failed"),
            ],
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
        output = "{}" if command == "sudo -n snap get -d system" else ""
        return subprocess.CompletedProcess([], 0, output)

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
        "sudo -n snap get -d system",
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
