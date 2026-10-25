"""Post-deployment Ubuntu Core data disk setup."""

import json
import shlex
import time

from testflinger_device_connectors.devices import ProvisioningError


def plan_data_disks(machine, devices):
    """Select supported non-boot physical data disks before touching any disk.

    The first version supports one ext4 partition per disk, on any number of
    physical disks. Reject complex layouts instead of silently applying only
    part of the MAAS configuration.
    """
    boot_disk = machine.get("boot_disk") or {}
    boot_id = boot_disk.get("id")
    boot_devices = [
        device
        for device in devices
        if device.get("id") == boot_id and device.get("type") == "physical"
    ]
    if boot_id is None or len(boot_devices) != 1:
        raise ProvisioningError("MAAS machine has no physical boot disk")
    boot_serial = boot_devices[0].get("serial")
    if not boot_serial or (
        boot_disk.get("serial") and boot_disk["serial"] != boot_serial
    ):
        raise ProvisioningError(
            "MAAS boot disk serial does not match inventory"
        )
    plans = []
    for device in devices:
        if device.get("type") != "physical" or device.get("id") == boot_id:
            continue
        partitions = device.get("partitions") or []
        if not partitions and not device.get("filesystem"):
            continue
        path = device.get("id_path")
        serial = device.get("serial")
        if not serial or not path or not path.startswith("/dev/disk/by-id/"):
            raise ProvisioningError(
                "Data disk needs a serial and a stable by-id path"
            )
        if serial == boot_serial or path == boot_devices[0].get("id_path"):
            raise ProvisioningError(
                "Data disk matches MAAS boot disk serial or path"
            )
        if len(partitions) != 1 or device.get("filesystem"):
            raise ProvisioningError(
                "Unsupported UC data disk layout: expected one partition"
            )
        filesystem = partitions[0].get("filesystem") or {}
        if filesystem.get("fstype") != "ext4":
            raise ProvisioningError(
                "Unsupported UC data disk filesystem: expected ext4"
            )
        if partitions[0].get("bootable") or filesystem.get("mount_point"):
            raise ProvisioningError(
                "Unsupported UC data disk: bootable or mounted partition"
            )

        label = filesystem.get("label") or ""
        if len(label.encode()) > 16 or any(
            c in label for c in ("/", "\n", "\r")
        ):
            raise ProvisioningError("Unsupported UC data disk ext4 label")
        plans.append({"serial": serial, "path": path, "label": label})
    if len({p["path"] for p in plans}) != len(plans) or len(
        {p["serial"] for p in plans}
    ) != len(plans):
        raise ProvisioningError("Duplicate data disk identity in MAAS")
    return plans


def apply_data_disk(ssh, disk):
    """Apply a pre-validated plan on a deployed Ubuntu Core DUT."""
    path = shlex.quote(disk["path"])
    query = (
        "sudo -n lsblk -T -J -b "
        "-o PATH,TYPE,SERIAL,FSTYPE,LABEL,SIZE,MOUNTPOINTS "
        f"-- {path}"
    )

    def inspect():
        try:
            roots = json.loads(ssh(query).stdout)["blockdevices"]
        except (ValueError, KeyError, TypeError) as error:
            raise ProvisioningError(
                "Invalid lsblk response from Ubuntu Core"
            ) from error
        if len(roots) != 1 or roots[0].get("type") != "disk":
            raise ProvisioningError(
                "UC data device is not a single physical disk"
            )
        root = roots[0]
        if (root.get("serial") or "").strip() != disk["serial"]:
            raise ProvisioningError("UC disk serial does not match MAAS")
        if any(
            child.get("label")
            in {"ubuntu-boot", "ubuntu-data", "ubuntu-seed", "ubuntu-save"}
            for child in root.get("children") or []
        ):
            raise ProvisioningError(
                "Refusing to alter an Ubuntu Core system disk"
            )
        return root

    root = inspect()
    children = root.get("children") or []
    if children:
        if (
            len(children) == 1
            and children[0].get("type") == "part"
            and children[0].get("fstype") == "ext4"
            and (children[0].get("label") or "") == disk["label"]
            and not any(children[0].get("mountpoints") or [])
        ):
            return
        raise ProvisioningError(
            "UC data disk has an unexpected existing layout"
        )
    if root.get("fstype") or any(root.get("mountpoints") or []):
        raise ProvisioningError("UC data disk is already formatted or mounted")
    if ssh(f"sudo -n wipefs --no-act {path}").stdout.strip():
        raise ProvisioningError(
            "UC data disk contains a partition table or signature"
        )

    # The model has one full-disk ext4 partition. Only do this after checking
    # the disk serial and proving the actual disk is completely blank.
    ssh(
        f"sudo -n sfdisk --wipe=never {path}", input_data="label: gpt\n\n,,L\n"
    )
    ssh("sudo -n udevadm settle")
    root = inspect()
    children = root.get("children") or []
    if (
        len(children) != 1
        or children[0].get("type") != "part"
        or children[0].get("fstype")
    ):
        raise ProvisioningError(
            "UC data partition was not created as expected"
        )
    partition = children[0].get("path")
    if not partition or not partition.startswith("/dev/"):
        raise ProvisioningError("UC data partition has no block device path")
    command = "sudo -n mkfs.ext4"
    if disk["label"]:
        command += f" -L {shlex.quote(disk['label'])}"
    ssh(f"{command} {shlex.quote(partition)}")
    root = inspect()
    children = root.get("children") or []
    if (
        len(children) == 1
        and children[0].get("path") == partition
        and children[0].get("type") == "part"
        and children[0].get("fstype") == "ext4"
        and (children[0].get("label") or "") == disk["label"]
        and not any(children[0].get("mountpoints") or [])
    ):
        return
    # lsblk's filesystem fields may lag behind mkfs (notably on removable
    # media). Probe the superblock directly, allowing a brief settling period.
    # Never retry the writes: only re-read the same verified disk/partition.
    fields = {}
    probe_error = None
    for attempt in range(3):
        if attempt:
            time.sleep(1)
            children = inspect().get("children") or []
        if (
            len(children) != 1
            or children[0].get("path") != partition
            or children[0].get("type") != "part"
            or any(children[0].get("mountpoints") or [])
        ):
            raise ProvisioningError(
                "UC data disk filesystem verification failed: "
                f"disk={disk['serial']}, lsblk={children!r}"
            )
        try:
            probe = ssh(
                f"sudo -n blkid -p -o export -- {shlex.quote(partition)}"
            )
            fields = dict(
                line.split("=", 1)
                for line in probe.stdout.splitlines()
                if "=" in line
            )
            probe_error = None
        except ProvisioningError as error:
            probe_error = str(error)
        if (
            fields.get("TYPE") == "ext4"
            and fields.get("LABEL", "") == disk["label"]
        ):
            return
    raise ProvisioningError(
        "UC data disk filesystem verification failed: "
        f"disk={disk['serial']}, partition={partition}, "
        f"lsblk={children!r}, blkid={fields!r}, probe_error={probe_error!r}"
    )
