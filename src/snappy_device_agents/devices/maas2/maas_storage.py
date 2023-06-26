# Copyright (C) 2023 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Ubuntu MaaS 2.x storage provisioning code."""

import logging
import subprocess
import collections
import json
import math


logger = logging.getLogger()


class MaasStorageError(Exception):
    def __init__(self, message):
        super().__init__(message)


class MaasStorage:
    def __init__(self, maas_user, node_id, storage_data):
        self.maas_user = maas_user
        self.node_id = node_id
        self.device_list = storage_data
        self.node_info = self._node_read()
        self.block_ids = None
        self.partition_list = None

    def _logger_debug(self, message):
        logger.debug("MAAS: {}".format(message))

    def _logger_info(self, message):
        logger.info("MAAS: {}".format(message))

    def _node_read(self):
        cmd = ["maas", self.maas_user, "block-devices", "read", self.node_id]
        return self.call_cmd(cmd, output_json=True)

    @staticmethod
    def call_cmd(cmd, output_json=False):
        logging.i(cmd)
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False
        )
        if proc.returncode:
            raise MaasStorageError(proc.stdout.decode())

        if proc.stdout:
            output = proc.stdout.decode()

            if output_json:
                data = json.loads(output)
            else:
                data = output

            return data

    @staticmethod
    def convert_size_to_bytes(size_str):
        """Convert given sizes to bytes; case insensitive."""
        size_str = size_str.upper()
        if "T" in size_str:
            return round(float(size_str.replace("T", "")) * (1000**4))
        elif "G" in size_str:
            return round(float(size_str.replace("G", "")) * (1000**3))
        elif "M" in size_str:
            return round(float(size_str.replace("M", "")) * (1000**2))
        elif "K" in size_str:
            return round(float(size_str.replace("K", "")) * 1000)
        elif "B" in size_str:
            return int(size_str.replace("B", ""))
        else:
            try:
                # attempt to convert the size string to an integer
                return int(size_str)
            except ValueError:
                raise MaasStorageError(
                    "Sizes must end in T, G, M, K, B, or be an integer "
                    "when no unit is provided."
                )

    def configure_node_storage(self):
        """Configure the node's storage layout, from provisioning data."""
        self._logger_info(self.node_info)  # debugging
        self.assign_top_level_parent()
        self.partition_list = self.gather_partitions()

        self.block_ids = self.parse_block_devices()

        self.map_block_ids()

        self.create_partition_sizes()

        devs_by_type = self.group_by_type()

        # clear existing storage on node
        self.clear_storage_config()

        # apply configured storage to node
        self.process_by_type(devs_by_type)

    def clear_storage_config(self):
        """Clear the node's exisitng storage configuration."""
        self._logger_info("Clearing existing storage configuration:")
        for blkdev in self.node_info:
            if blkdev["type"] == "virtual":
                continue
            for partition in blkdev["partitions"]:
                self.call_cmd(
                    [
                        "maas",
                        self.maas_user,
                        "partition",
                        "delete",
                        self.node_id,
                        str(blkdev["id"]),
                        str(partition["id"]),
                    ]
                )
            if blkdev["filesystem"] is not None:
                if blkdev["filesystem"]["mount_point"] is not None:
                    self.call_cmd(
                        [
                            "maas",
                            self.maas_user,
                            "block-device",
                            "unmount",
                            self.node_id,
                            str(blkdev["id"]),
                        ]
                    )
                self.call_cmd(
                    [
                        "maas",
                        self.maas_user,
                        "block-device",
                        "unformat",
                        self.node_id,
                        str(blkdev["id"]),
                    ]
                )
                self.call_cmd(
                    [
                        "maas",
                        self.maas_user,
                        "block-device",
                        "unformat",
                        self.node_id,
                        str(blkdev["id"]),
                    ]
                )

    def assign_top_level_parent(self):
        """Transverse device hierarchy to determine each device's parent
        disk."""
        dev_dict = {dev["id"]: dev for dev in self.device_list}
        for dev in self.device_list:
            parent_id = dev.get("device") or dev.get("volume")

            if dev["type"] == "disk":
                # keep 'top_level_parent' key for consistency
                dev["top_level_parent"] = dev["id"]

            while parent_id and parent_id in dev_dict:
                parent = dev_dict[parent_id]
                parent_id = parent.get("device") or parent.get("volume")
                if parent["type"] == "disk":
                    dev["top_level_parent"] = parent["id"]

    def gather_partitions(self):
        """Tally partition size requirements for block-device selection."""
        partitions = collections.defaultdict(list)

        for dev in self.device_list:
            if dev["type"] == "partition":
                # convert size to bytes before appending to the list
                partitions[dev["top_level_parent"]].append(
                    self.convert_size_to_bytes(dev["size"])
                )

        # summing up sizes of each disk's partitions
        partition_sizes = {
            devid: sum(partitions) for devid, partitions in partitions.items()
        }

        return partition_sizes

    def parse_block_devices(self):
        """Find appropriate node block-device for use in layout."""
        block_ids = {}
        mapped_block_ids = set()

        for dev_id, size in self.partition_list.items():
            self._logger_info(f"Comparing size: Partition: {size}")
            for blkdev in self.node_info:
                if (
                    blkdev["type"] != "physical"
                    or blkdev["id"] in mapped_block_ids
                ):
                    continue

                size_bd = int(blkdev["size"])
                self._logger_info(
                    f"Comparing size: Partition: {size}, "
                    f"Block Device: {size_bd}"
                )

                if size <= size_bd:
                    # map disk_id to block device id
                    block_ids[dev_id] = blkdev["id"]
                    mapped_block_ids.add(blkdev["id"])
                    break
            else:
                raise MaasStorageError(
                    "No suitable block-device found for partition "
                    f"{dev_id} with size {size} bytes"
                )
        return block_ids

    def map_block_ids(self):
        """Map parent disks to actual node block-device."""
        for dev in self.device_list:
            block_id = self.block_ids.get(dev["top_level_parent"])
            if block_id is not None:
                dev["top_level_parent_block_id"] = str(block_id)

    def validate_alloc_pct_values(self):
        """Sanity check partition allocation percentages."""
        alloc_pct_values = collections.defaultdict(int)

        for dev in self.device_list:
            if dev["type"] == "partition":
                # add pct together (default to 0 if unnused)
                alloc_pct_values[dev["top_level_parent"]] += dev.get(
                    "alloc_pct", 0
                )

        for dev_id, alloc_pct in alloc_pct_values.items():
            if alloc_pct > 100:
                raise MaasStorageError(
                    "The total percentage of the partitions on disk "
                    f"'{dev_id}' exceeds 100."
                )

    def create_partition_sizes(self):
        """Calculate actual partition size to write to disk."""
        self.validate_alloc_pct_values()

        for dev in self.device_list:
            if dev["type"] == "partition":
                # find corresponding block device
                for blkdev in self.node_info:
                    if blkdev["id"] == self.block_ids[dev["top_level_parent"]]:
                        # get the total size of the block device in bytes
                        total_size = int(blkdev["size"])
                        break

                if "alloc_pct" in dev:
                    # round pct up if necessary
                    dev["size"] = str(
                        math.ceil((total_size * dev.get("alloc_pct", 0)) / 100)
                    )
                else:
                    if "size" not in dev:
                        raise ValueError(
                            f"Partition '{dev['id']}' does not have an "
                            "alloc_pct or size value."
                        )
                    else:
                        # default to minimum required partition size
                        dev["size"] = self.convert_size_to_bytes(dev["size"])

    def group_by_type(self):
        """Group storage device by type for processing."""
        devs_by_type = collections.defaultdict(list)

        for dev in self.device_list:
            devs_by_type[dev["type"]].append(dev)

        return devs_by_type

    def process_by_type(self, devs_by_type):
        """Process each storage type together in dependancy sequence."""
        # order in which storage types are processed
        type_order = ["disk", "partition", "format", "mount"]
        # maps the type of a disk (like 'disk', 'partition', etc.)
        # to the corresponding function that processes it.
        type_to_method = {
            "disk": self.process_disk,
            "partition": self.process_partition,
            "mount": self.process_mount,
            "format": self.process_format,
        }
        part_data = {}

        # batch process storage devices
        for type_ in type_order:
            devices = devs_by_type.get(type_)
            if devices:
                self._logger_info(f"Processing type '{type_}':")
                for dev in devices:
                    try:
                        if type_ == "partition":
                            part_data[dev["id"]] = type_to_method[type_](dev)
                        else:
                            type_to_method[type_](dev)
                    # do not proceed to subsequent/child types
                    except MaasStorageError as error:
                        raise MaasStorageError(
                            f"Unable to process device: {dev} "
                            f"of type: {type_}"
                        ) from error

    def _set_boot_disk(self, block_id):
        """Mark node block-device as boot disk."""
        self._logger_info(f"Setting boot disk {block_id}")
        # self.call_cmd(
        self.call_cmd(
            [
                "maas",
                self.maas_user,
                "block-device",
                "set-boot-disk",
                self.node_id,
                block_id,
            ]
        )

    def _get_child_device(self, parent_device):
        """Get children devices from parent device."""
        children = []
        for dev in self.device_list:
            if dev["top_level_parent"] == parent_device["id"]:
                children.append(dev)
        return children

    def process_disk(self, device):
        """Process block level storage (disks)."""
        self._logger_info("Disk:")
        self._logger_info(
            {
                "device_id": device["id"],
                "name": device["name"],
                "number": device.get("number"),
                "block-id": device["top_level_parent_block_id"],
            }
        )
        # find boot mounts on child types
        children = self._get_child_device(device)

        for child in children:
            if child["type"] == "mount" and "/boot" in child["path"]:
                self._logger_info(
                    f"Disk {device['id']} has a child mount with "
                    f"'boot' in its path: {child['path']}"
                )
                self._set_boot_disk(device["top_level_parent_block_id"])
                break
        # apply disk name
        if "name" in device:
            # self.call_cmd(
            self.call_cmd(
                [
                    "maas",
                    self.maas_user,
                    "block-device",
                    "update",
                    self.node_id,
                    device["top_level_parent_block_id"],
                    f"name={device['name']}",
                ]
            )

    def _create_partition(self, device):
        """Create parition on disk and return the resulting parition-id."""
        cmd = [
            "maas",
            self.maas_user,
            "partitions",
            "create",
            self.node_id,
            device["top_level_parent_block_id"],
            f"size={device['size']}",
        ]

        return self.call_cmd(cmd)

    def process_partition(self, device):
        """Process given partitions from the storage layout config."""
        self._logger_info("Partition:")
        self._logger_info(
            {
                "device_id": device["id"],
                "size": device["size"],
                "number": device.get("number"),
                "parent disk": device["top_level_parent"],
                "parent block-id": device["top_level_parent_block_id"],
            }
        )
        partition_id = self._create_partition(device)
        device["partition_id"] = partition_id
        # device['partition_id'] = device['id']

    def _get_format_partition_id(self, volume):
        """Get the partition id from the specified format."""
        for dev in self.device_list:
            if volume == dev["id"]:
                return dev["partition_id"]

    def process_format(self, device):
        """Process given parition formats from the storage layout config."""
        self._logger_info("Format:")
        self._logger_info(
            {
                "device_id": device["id"],
                "fstype": device["fstype"],
                "label": device["label"],
                "parent disk": device["top_level_parent"],
                "parent block-id": device["top_level_parent_block_id"],
            }
        )
        # format partition
        if "volume" in device:
            partition_id = self._get_format_partition_id(device["volume"])
            self.call_cmd(
                [
                    "maas",
                    self.maas_user,
                    "partition",
                    "format",
                    self.node_id,
                    device["top_level_parent_block_id"],
                    partition_id,
                    f"fstype={device['fstype']}",
                    f"label={device['label']}",
                ]
            )
        # format blkdev
        else:
            self.call_cmd(
                [
                    "maas",
                    self.maas_user,
                    "partition",
                    "format",
                    self.node_id,
                    device["top_level_parent_block_id"],
                    f"fstype={device['fstype']}",
                    f"label={device['label']}",
                ]
            )

    def _get_mount_partition_id(self, device):
        """Get the partiton-id of the specified mount path."""
        for dev in self.device_list:
            if device == dev["id"]:
                return self._get_format_partition_id(dev["volume"])

    def process_mount(self, device):
        """Process given mounts/paths from the storage layout config."""
        self._logger_info("Mount:")
        self._logger_info(
            {
                "device_id": device["id"],
                "path": device["path"],
                "parent disk": device["top_level_parent"],
                "parent block-id": device["top_level_parent_block_id"],
            }
        )
        partition_id = self._get_mount_partition_id(device["device"])
        # mount on partition
        if partition_id:
            self._logger_info(f"  on partition_id: {partition_id}")
            self.call_cmd(
                [
                    "maas",
                    self.maas_user,
                    "partition",
                    "mount",
                    self.node_id,
                    device["top_level_parent_block_id"],
                    partition_id,
                    f"mount_point={device['path']}",
                ]
            )
        # mount on block-device
        else:
            self._logger_info(f"  on disk: {device['top_level_parent']}")
            self.call_cmd(
                [
                    "maas",
                    self.maas_user,
                    "block-device",
                    "mount",
                    self.node_id,
                    device["top_level_parent_block_id"],
                    f"mount_point={device['path']}",
                ]
            )
