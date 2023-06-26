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
        self.block_ids = {}
        self.partition_sizes = {}

    def _logger_debug(self, message):
        logger.debug("MAAS: {}".format(message))

    def _logger_info(self, message):
        logger.info("MAAS: {}".format(message))

    def _node_read(self):
        """Read node block-devices.

        :return: the node's block device information
        """
        cmd = ["maas", self.maas_user, "block-devices", "read", self.node_id]
        return self.call_cmd(cmd, output_json=True)

    @staticmethod
    def call_cmd(cmd, output_json=False):
        """Run a command and return the output.

        :param cmd: command to run
        :param output_json: output the result as JSON
        :return: subprocess stdout
        """
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False
        )
        if proc.returncode:
            raise MaasStorageError(proc.stdout.decode())

        if proc.stdout:
            output = proc.stdout.decode()

            if output_json:
                return json.loads(output)

            return output

    @staticmethod
    def convert_size_to_bytes(size_str):
        """Convert given sizes to bytes; case insensitive.

        :param size_str: the size string to convert
        :return: the size in bytes
        :raises MaasStorageError: on invalid size unit/type
        """
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
        self._logger_info("Configuring node storage")
        # map top level parent disk to every device
        self.assign_parent_disk()
        # tally partition requirements for each disk
        self.gather_partitions()
        # find appropriate block devices for each partition
        self.parse_block_devices()
        # map block ids to top level parents
        self.map_block_ids()
        # calculate partition sizes
        self.create_partition_sizes()
        # group devices by type
        devs_by_type = self.group_by_type()
        # clear existing storage on node
        self.clear_storage_config()
        # apply configured storage to node
        self.process_by_type(devs_by_type)

    def clear_storage_config(self):
        """Clear the node's exisitng storage configuration."""
        self._logger_info("Clearing existing storage configuration:")
        for block_dev in self.node_info:
            if block_dev["type"] == "virtual":
                continue
            for partition in block_dev["partitions"]:
                self.call_cmd(
                    [
                        "maas",
                        self.maas_user,
                        "partition",
                        "delete",
                        self.node_id,
                        str(block_dev["id"]),
                        str(partition["id"]),
                    ]
                )
            if block_dev["filesystem"] is not None:
                if block_dev["filesystem"]["mount_point"] is not None:
                    self.call_cmd(
                        [
                            "maas",
                            self.maas_user,
                            "block-device",
                            "unmount",
                            self.node_id,
                            str(block_dev["id"]),
                        ]
                    )
                self.call_cmd(
                    [
                        "maas",
                        self.maas_user,
                        "block-device",
                        "unformat",
                        self.node_id,
                        str(block_dev["id"]),
                    ]
                )

    def assign_parent_disk(self):
        """Transverse device hierarchy to determine each device's parent
        disk."""
        dev_dict = {dev["id"]: dev for dev in self.device_list}
        for dev in self.device_list:
            parent_id = dev.get("device") or dev.get("volume")

            if dev["type"] == "disk":
                # keep 'parent_disk' key for consistency
                dev["parent_disk"] = dev["id"]

            while parent_id and parent_id in dev_dict:
                parent = dev_dict[parent_id]
                parent_id = parent.get("device") or parent.get("volume")
                if parent["type"] == "disk":
                    dev["parent_disk"] = parent["id"]

    def gather_partitions(self):
        """Tally partition size requirements for block-device selection."""
        partitions = collections.defaultdict(list)

        for dev in self.device_list:
            if dev["type"] == "partition":
                # convert size to bytes before appending to the list
                partitions[dev["parent_disk"]].append(
                    self.convert_size_to_bytes(dev["size"])
                )

        # summing up sizes of each disk's partitions
        self.partition_sizes = {
            devid: sum(partitions) for devid, partitions in partitions.items()
        }

    def _select_block_dev(self, partition_id, partition_size):
        """Find a suitable block device for the given partition.

        :param partition_id: the id of the partition
        :param partition_size: the size of the partition
        :return: the id of a suitable block device if found
        :raises MaasStorageError: if no suitable block device is found
        """
        for block_dev in self.node_info:
            if (
                block_dev["type"] == "physical"
                and block_dev["id"] not in self.block_ids.values()
                and partition_size <= int(block_dev["size"])
            ):
                return block_dev["id"]

        raise MaasStorageError(
            "No suitable block-device found for partition "
            f"{partition_id} with size {partition_size} bytes"
        )

    def parse_block_devices(self):
        """Find appropriate node block-device for use in layout."""
        for partition_id, partition_size in self.partition_sizes.items():
            self._logger_info(f"Comparing size: Partition: {partition_size}")
            block_device_id = self._select_block_dev(
                partition_id, partition_size
            )

            # map partition id to block device id
            self.block_ids[partition_id] = block_device_id

    def map_block_ids(self):
        """Map parent disks to actual node block-devices.

        Updates self.device_list with "parent_disk_blkid".
        """
        for dev in self.device_list:
            block_id = self.block_ids.get(dev["parent_disk"])
            if block_id is not None:
                dev["parent_disk_blkid"] = str(block_id)

    def _validate_alloc_pct_values(self):
        """Sanity check partition allocation percentages."""
        alloc_pct_values = collections.defaultdict(int)

        for dev in self.device_list:
            if dev["type"] == "partition":
                # add pct together (default to 0 if unnused)
                alloc_pct_values[dev["parent_disk"]] += dev.get(
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
        self._validate_alloc_pct_values()

        for dev in self.device_list:
            if dev["type"] == "partition":
                # find corresponding block device
                for block_dev in self.node_info:
                    if block_dev["id"] == self.block_ids[dev["parent_disk"]]:
                        # get the total size of the block device in bytes
                        total_size = int(block_dev["size"])
                        break

                if "alloc_pct" in dev:
                    # avoid under-allocating space
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
        """Group storage devices by type for processing.

        :return: dict with device types as keys and lists of devices as values
        """
        devs_by_type = collections.defaultdict(list)

        for dev in self.device_list:
            devs_by_type[dev["type"]].append(dev)

        return devs_by_type

    def process_by_type(self, devs_by_type):
        """Process each storage type together in sequence.

        :param devs_by_type: dict with device types as keys and
            lists of devices as values
        :raises MaasStorageError: if an error occurs during device processing
        """
        # order in which storage types are processed
        type_order = ["disk", "partition", "format", "mount"]
        # maps the device type to the method that processes it
        type_to_method = {
            "disk": self.process_disk,
            "partition": self.process_partition,
            "mount": self.process_mount,
            "format": self.process_format,
        }
        partn_data = {}

        for type_ in type_order:
            devices = devs_by_type.get(type_)
            if devices:
                self._logger_info(f"Processing type '{type_}':")
                for dev in devices:
                    try:
                        if type_ == "partition":
                            partn_data[dev["id"]] = type_to_method[type_](dev)
                        else:
                            type_to_method[type_](dev)
                    # do not proceed to subsequent/child types
                    except MaasStorageError as error:
                        raise MaasStorageError(
                            f"Unable to process device: {dev} "
                            f"of type: {type_}"
                        ) from error

    def _set_boot_disk(self, block_id):
        """Mark a node block-device as the boot disk.

        :param block_id: ID of the block-device
        """
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
        """Get the children devices from a parent device.

        :param parent_device: the parent device
        :return: list of children devices
        """
        children = []
        for dev in self.device_list:
            if dev["parent_disk"] == parent_device["id"]:
                children.append(dev)
        return children

    def process_disk(self, device):
        """Process block-level storage (disks).

        :param device: the disk device to process
        """
        self._logger_info("Disk:")
        self._logger_info(
            {
                "device_id": device["id"],
                "name": device["name"],
                "number": device.get("number"),
                "block-id": device["parent_disk_blkid"],
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
                self._set_boot_disk(device["parent_disk_blkid"])
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
                    device["parent_disk_blkid"],
                    f"name={device['name']}",
                ]
            )

    def _create_partition(self, device):
        """Create a partition on a disk and return the resulting partition ID.

        :param device: the partition device
        :return: the resulting node partition ID
        """
        cmd = [
            "maas",
            self.maas_user,
            "partitions",
            "create",
            self.node_id,
            device["parent_disk_blkid"],
            f"size={device['size']}",
        ]

        return self.call_cmd(cmd, output_json=True)

    def process_partition(self, device):
        """Process a partition from the storage layout config.

        :param device: the partition device to process
        """
        self._logger_info("Partition:")
        self._logger_info(
            {
                "device_id": device["id"],
                "size": device["size"],
                "number": device.get("number"),
                "parent disk": device["parent_disk"],
                "parent disk block-id": device["parent_disk_blkid"],
            }
        )
        partition_data = self._create_partition(device)
        device["partition_id"] = str(partition_data["id"])

    def _get_format_partition_id(self, volume):
        """Get the partition ID from the specified format.

        :param volume: the volume ID
        :return: the node partition ID
        """
        for dev in self.device_list:
            if volume == dev["id"]:
                return dev["partition_id"]

    def process_format(self, device):
        """Process a partition format from the storage layout config.

        :param device: the format device to process
        """
        self._logger_info("Format:")
        self._logger_info(
            {
                "device_id": device["id"],
                "fstype": device["fstype"],
                "label": device["label"],
                "parent disk": device["parent_disk"],
                "parent disk block-id": device["parent_disk_blkid"],
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
                    device["parent_disk_blkid"],
                    partition_id,
                    f"fstype={device['fstype']}",
                    f"label={device['label']}",
                ]
            )
        # format block-device
        else:
            self.call_cmd(
                [
                    "maas",
                    self.maas_user,
                    "partition",
                    "format",
                    self.node_id,
                    device["parent_disk_blkid"],
                    f"fstype={device['fstype']}",
                    f"label={device['label']}",
                ]
            )

    def _get_mount_partition_id(self, device):
        """Get the partition ID from the specified mount path.

        :param device: the mount device
        :return: the partition ID
        """
        for dev in self.device_list:
            if device == dev["id"]:
                return self._get_format_partition_id(dev["volume"])

    def process_mount(self, device):
        """Process a mount path from the storage layout config.

        :param device: the mount device to process
        """
        self._logger_info("Mount:")
        self._logger_info(
            {
                "device_id": device["id"],
                "path": device["path"],
                "parent disk": device["parent_disk"],
                "parent disk block-id": device["parent_disk_blkid"],
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
                    device["parent_disk_blkid"],
                    partition_id,
                    f"mount_point={device['path']}",
                ]
            )
        # mount on block-device
        else:
            self._logger_info(f"  on disk: {device['parent_disk']}")
            self.call_cmd(
                [
                    "maas",
                    self.maas_user,
                    "block-device",
                    "mount",
                    self.node_id,
                    device["parent_disk_blkid"],
                    f"mount_point={device['path']}",
                ]
            )
