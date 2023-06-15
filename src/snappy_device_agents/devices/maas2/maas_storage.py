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

"""Ubuntu MaaS 2.x CLI support code."""

import logging
import subprocess
import collections

from snappy_device_agents.devices import ProvisioningError

logger = logging.getLogger()


class ConfigureMaasStorage:
    def __init__(self, maas_user, node_id):
        self.maas_user = maas_user
        self.node_id = node_id
        self.node_info = self._node_read(maas_user, node_id)

    def _logger_info(self, message):
        logger.info("MAAS: {}".format(message))

    def _node_read(self):
        cmd = ["maas", self.maas_user, "machine", "read", self.node_id]
        return self.call_cmd(cmd)

    def _entries_of_type(self, config, entry_type):
        """Get all of the config entries of a specific type."""
        return [entry for entry in config if entry["type"] == entry_type]

    def parse_disk_types(self, disk_list):
        disks_by_type = collections.defaultdict(list)
        disk_dict = {disk['id']: disk for disk in disk_list}
        for disk in disk_list:
            parent_id = disk.get('device') or disk.get('volume')

            # assign tlp to disk
            if disk['type'] == 'disk':
                disk['top_level_parent'] = disk['id']  # drop in block_id

            while parent_id and parent_id in disk_dict:
                parent = disk_dict[parent_id]
                parent_id = parent.get('device') or parent.get('volume')
                if parent['type'] == 'disk':
                    disk['top_level_parent'] = parent['id']  # drop in block_id

            disks_by_type[disk["type"]].append(disk)

        return disks_by_type

    def call_cmd(self, cmd):
        """subprocess placeholder"""
        self._logger_info("Configuring node storage")
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False
        )
        if proc.returncode:
            self._logger_error(f"maas error running: {' '.join(cmd)}")
            raise ProvisioningError(proc.stdout.decode())

    # def map_bucket_disks_to_machine_disks(self):
    #     """Go from abstract bucket disks to concrete machine disks.

    #     This maps the indexes of disks in the config to blockdevices on
    #     this specific machine in MAAS, so we can refer to the blockdevices
    #     in the API later on.

    #     We iterate over the set of disks referenced in the machine's bucket,
    #     and find a disk from the MAAS machine that matches the disk's
    #     characteristics.  When we find a matching disk, we record that
    #     in the disks_to_blockdevices map, and add it to the used list
    #     so we don't try to use the same blockdevice more than once.

    #     The mapping we end up with depends on the order of disks from
    #     the config, which can change, since it's a dictionary in python,
    #     and the order of the blockdevices listed in MAAS, which may or
    #     may not be stable.  This means we may get different config disk
    #     to actual disk mappings for the same config applied to the same
    #     machine when this is run multiple times.  That's ok - we don't
    #     care which physical disk is chosen, as long as it has matching
    #     characteristics.
    #     """
    #     bucket = self.buckets[self.get_bucket_for_machine(self.node_info["fqdn"])]
    #     used = []
    #     return {
    #         disk_id: self.find_matching_blockdevice(self.node_info, disk_info, used)
    #         for disk_id, disk_info in bucket["hardware"]["disks"].items()
    #     }

    def map_disk_device_to_blockdevice(
        self, disk_config, config_disk_to_blockdevice
    ):
        """Maps the 'id' of each disk entry in the disk config
        to a specific blockdevice on this specific machine in MAAS.
        That gives us the ID we need to refer to the specific block
        device during API calls to MAAS. It's handy to have this map
        in addition to the "bucket config disk id" -> blockdevice map,
        because the disk config clauses all refer to this disk device
        id, not the bucket config disk id.
        """
        disk_device_to_blockdevice = {}
        for disk in self._entries_of_type(disk_config, "disk"):
            blockdevice = config_disk_to_blockdevice[disk["disk"]]
            disk_device_to_blockdevice[disk["id"]] = blockdevice
        return disk_device_to_blockdevice

    def humanized_size(self, num, system_unit=1024):
        for suffix in ["", "K", "M", "G", "T", "P", "E", "Z"]:
            if num < system_unit:
                return "%d%s" % (round(num), suffix)
            num = num / system_unit
        return "%dY" % (round(num))

    def round_disk_size(self, disk_size):
        return round(float(disk_size) / (5 * 1000**3)) * (5 * 1000**3)

    def find_matching_blockdevice(self, disk, used):  # <------
        """Match MAAS blockdevice and config device."""
        if disk["businfo"] is None:
            for blockdevice in self.node_info["blockdevice_set"]:
                if blockdevice["type"] != "physical":
                    continue
                size = self.humanized_size(
                    self.round_disk_size(blockdevice["size"]), system_unit=1000
                )
                if disk["size"] != size:
                    continue
                if (
                    disk["tags"] == blockdevice["tags"]
                    and blockdevice["id"] not in used
                ):
                    used.append(blockdevice["id"])
                    return blockdevice
            raise KeyError("no blockdevice found for disk %s" % (disk))

        block_device = self._match_block_device(self.node_info, disk, used)
        if block_device:
            return block_device
        raise KeyError("no blockdevice found for disk %s" % (disk))

    def _match_block_device(self, disk, used_devices):
        # Post MAAS 2.4.0 implementation if matching is performed by using
        # using an id_path retrieved via businfo
        device_id_paths = self.get_block_id_paths_by_businfo(
            str(self.node_info["system_id"]), disk["businfo"]
        )
        for blockdevice in self.node_info["blockdevice_set"]:
            if blockdevice["type"] != "physical":
                continue
            if (
                blockdevice["id_path"] in device_id_paths
                and blockdevice["id"] not in used_devices
            ):
                used_devices.append(blockdevice["id"])
                return blockdevice
            elif (
                blockdevice["serial"] in device_id_paths
                and blockdevice["id"] not in used_devices
            ):
                used_devices.append(blockdevice["id"])
                return blockdevice

    def clear_storage_config(self):
        blockdevice_set = self.read_blockdevices()
        for blockdevice in blockdevice_set:
            if blockdevice["type"] == "virtual":
                continue
            for partition in blockdevice["partitions"]:
                self.call_cmd(
                    [
                        "maas",
                        self.maas_user,
                        "partition",
                        "delete",
                        self.node_id,
                        str(blockdevice["id"]),
                        str(partition["id"]),
                    ]
                )
            if blockdevice["filesystem"] is not None:
                if blockdevice["filesystem"]["mount_point"] is not None:
                    self.call_cmd(
                        [
                            "maas",
                            self.maas_user,
                            "block-device",
                            "unmount",
                            self.node_id,
                            str(blockdevice["id"]),
                        ]
                    )

                self.call_cmd(
                    [
                        "maas",
                        self.maas_user,
                        "block-device",
                        "unformat",
                        self.node_id,
                        blockdevice["id"],
                    ]
                )
                self.call_cmd(
                    [
                        "maas",
                        self.maas_user,
                        "block-device",
                        "unformat",
                        self.node_id,
                        str(blockdevice["id"]),
                    ]
                )

    def mount_blockdevice(self, blockdevice_id, mount_point):
        self.call_cmd(
            [
                "maas",
                self.maas_user,
                "block-device",
                "mount",
                self.node_id,
                blockdevice_id,
                f"mount_point={mount_point}",
            ]
        )

    def mount_partition(self, blockdevice_id, partition_id, mount_point):
        self.call_cmd(
            [
                "maas",
                self.maas_user,
                "partition",
                "mount",
                self.node_id,
                blockdevice_id,
                partition_id,
                f"mount_point={mount_point}",
            ]
        )

    def format_partition(self, blockdevice_id, partition_id, fstype, label):
        self.call_cmd(
            [
                "maas",
                self.maas_user,
                "partition",
                "format",
                self.node_id,
                blockdevice_id,
                partition_id,
                f"fstype={fstype}",
                f"label={label}",
            ]
        )

    def create_partition(self, blockdevice_id, size=None):
        cmd = [
            "maas",
            self.maas_user,
            "partitions",
            "create",
            self.node_id,
            blockdevice_id,
        ]
        if size is not None:
            cmd.append(f"size={size}")
        return self.call_cmd(cmd)

    def set_boot_disk(self, blockdevice_id):
        self.call_cmd(
            [
                "maas",
                self.maas_user,
                "block-device",
                "set-boot-disk",
                self.node_id,
                blockdevice_id,
            ]
        )

    def update_blockdevice(self, blockdevice_id, opts=None):
        """Update a block-device.

        :param str self.maas_user: The maas cli profile to use.
        :param str self.node_id: The self.node_id of the machine.
        :param str blockdevice_id: The id of the block-device.
        :param dict opts: A dictionary of options to apply.
        :returns: The updated MAAS API block-device dictionary.
        """
        cmd = [
            "maas",
            self.maas_user,
            "block-device",
            "update",
            self.node_id,
            blockdevice_id,
        ]
        if opts is not None:
            for k, v in opts.items():
                cmd.append(f"{k}={v}")
        return self.call_cmd(cmd)

    def format_blockdevice(self, blockdevice_id, fstype, label):
        self.call_cmd(
            [
                "maas",
                self.maas_user,
                "block-device",
                "format",
                self.node_id,
                blockdevice_id,
                f"fstype={fstype}",
                f"label={label}",
            ]
        )

    def read_blockdevices(self):
        cmd = [
            "maas",
            self.maas_user,
            "block-devices",
            "read",
            self.node_id,
        ]
        return self.call_cmd(cmd)

    def get_disksize_real_value(self, value):
        """Sizes can use M, G, T suffixes."""
        try:
            real_value = str(int(value))
            return real_value
        except ValueError as error:
            for n, suffix in enumerate(["M", "G", "T"]):
                if value[-1].capitalize() == suffix:
                    return str(int(float(value[:-1]) * 1000 ** (n + 2)))
            raise error

    def partition_disks(self, disk_config, disk_device_to_blockdevice):
        """Partition the disks on a specific machine."""
        # Find and create the partitions on this disk
        partitions = self._entries_of_type(disk_config, "partition")
        partitions = sorted(partitions, key=lambda k: k["number"])
        # maps config partition ids to maas partition ids
        partition_map = {}
        for partition in partitions:
            disk_maas_id = disk_device_to_blockdevice[partition["device"]][
                "id"
            ]
            self._logger_info("Creating partition %s", partition["id"])
            # If size is not specified, all avaiable space is used
            if "size" not in partition or not partition["size"]:
                disksize_value = None
            else:
                disksize_value = self.get_disksize_real_value(
                    partition["size"]
                )

            partition_id = self.create_partition(
                self.self.maas_user,
                self.node_id,
                str(disk_maas_id),
                size=disksize_value,
            )["id"]
            partition_map[partition["id"]] = {
                "partition_id": partition_id,
                "blockdevice_id": disk_maas_id,
            }
        return partition_map

    def update_disks(self, disk_config, disk_device_to_blockdevice):
        """Update the settings for disks on a machine.

        :param str self.node_id: The self.node_id of the machine.
        :param list disk_config: The disk config for a machine.
        :param dict disk_device_to_blockdevice: maps config disk ids
            to maas API block-devices.
        """
        for disk in self._entries_of_type(disk_config, "disk"):
            if "boot" in disk and disk["boot"]:
                logging.warn(
                    "Setting boot disk only applies to"
                    " legacy (non-EFI) booting systems!"
                )
                self.set_boot_disk(
                    self.self.maas_user,
                    self.node_id,
                    str(disk_device_to_blockdevice[disk["id"]]["id"]),
                )
            if "name" in disk:
                self.update_blockdevice(
                    self.self.maas_user,
                    self.node_id,
                    str(disk_device_to_blockdevice[disk["id"]]["id"]),
                    opts={"name": disk["name"]},
                )

    def apply_formats(
        self, disk_config, partition_map, disk_device_to_blockdevice
    ):
        """Apply formats on the volumes of a specific machine."""
        # Format the partitions we created, or disks!
        for _format in self._entries_of_type(disk_config, "format"):
            self._logger_info("applying format %s", _format["id"])
            if _format["volume"] in partition_map:
                partition_info = partition_map[_format["volume"]]
                self.format_partition(
                    self.user_id,
                    self.node_id,
                    str(partition_info["blockdevice_id"]),
                    str(partition_info["partition_id"]),
                    _format["fstype"],
                    _format["label"],
                )
            else:
                device_info = disk_device_to_blockdevice[_format["volume"]]
                self.format_blockdevice(
                    self.user_id,
                    self.node_id,
                    str(device_info["id"]),
                    _format["fstype"],
                    _format["label"],
                )

    def create_mounts(
        self, disk_config, partition_map, disk_device_to_blockdevice
    ):
        """Create mounts on a specific machine."""
        # Create mounts for the formatted partitions
        # rename to get_config?
        for mount in self._entries_of_type(self.disk_config, "mount"):
            self._logger_info("applying mount %s", mount["id"])
            volume_name = mount["device"][:-7]  # strip _format
            if volume_name in partition_map:
                partition_info = partition_map[volume_name]
                self.mount_partition(
                    self.user_id,
                    self.node_id,
                    str(partition_info["blockdevice_id"]),
                    str(partition_info["partition_id"]),
                    mount["path"],
                )
            else:
                device_info = disk_device_to_blockdevice[volume_name]
                self.mount_blockdevice(
                    self.user_id,
                    self.node_id,
                    str(device_info["id"]),
                    mount["path"],
                )

    def setup_storage(self, config):
        """Setup storage on a specific machine."""
        self._logger_info("Clearing previous storage configuration")
        self.clear_storage_config()
        # config_disk_to_blockdevice = self.map_bucket_disks_to_machine_disks()
        disks_by_type = self.parse_disk_types()
        disk_device_to_blockdevice = self.map_disk_device_to_blockdevice(
            config["disks"], disks_by_type
        )
        # apply updates to the disks.
        self.update_disks(config["disks"], disk_device_to_blockdevice)
        # partition disks and keep map of config partitions
        # to partition ids in maas
        partition_map = self.partition_disks(
            config["disks"], disk_device_to_blockdevice
        )
        # format volumes and create mount points
        self.apply_formats(
            self.node_id,
            config["disks"],
            partition_map,
            disk_device_to_blockdevice,
        )
        self.create_mounts(
            self.node_id,
            # config["disks"],
            partition_map,
            disk_device_to_blockdevice,
        )
