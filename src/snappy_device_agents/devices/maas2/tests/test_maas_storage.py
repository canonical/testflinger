import pytest
import json
from maas_storage import MaasStorage, MaasStorageError
from unittest.mock import Mock, MagicMock, call


class MockMaasStorage(MaasStorage):
    """Enable mock subprocess calls."""

    def __init__(self, maas_user, node_id):
        super().__init__(maas_user, node_id)
        self.call_cmd_mock = Mock()

    def call_cmd(self, cmd, output_json=False):
        """Mock method to simulate the call_cmd method in the
        parent MaasStorage class.
        """

        if output_json:
            return json.loads(TestMaasStorage.node_info)
        else:
            # monkeypatch
            return self.call_cmd_mock(cmd)


class TestMaasStorage:
    """Test maas device agent storage module."""

    node_info = json.dumps(
        [
            {
                "id": 1,
                "name": "sda",
                "type": "physical",
                "size": "300000000000",
                "path": "/dev/disk/by-dname/sda",
                "filesystem": None,
                "partitions": [
                    {
                        "id": 10,
                        "type": "partition",
                        "size": "1000000000",
                        "parent_disk": 1,
                        "bootable": "true",
                        "filesystem": {
                            "mount_point": "/boot",
                            "fstype": "ext4",
                        },
                    }
                ],
            },
            {
                "id": 2,
                "name": "sdb",
                "type": "physical",
                "size": "400000000000",
                "path": "/dev/disk/by-dname/sdb",
                "filesystem": None,
                "partitions": [
                    {
                        "id": 20,
                        "type": "partition",
                        "size": "20000000000",
                        "parent_disk": 2,
                        "filesystem": {
                            "mount_point": "/data",
                            "fstype": "ext4",
                        },
                    }
                ],
            },
            {
                "id": 3,
                "name": "sdc",
                "type": "physical",
                "size": "900000000000",
                "path": "/dev/disk/by-dname/sdc",
                "filesystem": {"mount_point": "/backup", "fstype": "ext4"},
                "partitions": [],
            },
            {
                "id": 4,
                "type": "virtual",
            },
        ]
    )

    @pytest.fixture
    def maas_storage(self):
        """Provides a MockMaasStorage instance for testing."""
        maas_user = "maas_user"
        node_id = "node_id"
        yield MockMaasStorage(maas_user, node_id)

    def test_node_read(self, maas_storage):
        """Checks if 'node_read' correctly returns node block-devices."""
        node_info = maas_storage._node_read()
        assert node_info == json.loads(self.node_info)

    def test_call_cmd_output_json(self, maas_storage):
        """Test 'call_cmd' when output_json is True.
        Checks if the method correctly returns json data.
        """
        result = maas_storage.call_cmd(
            ["maas", "maas_user", "block-devices", "read", "node_id"],
            output_json=True,
        )
        assert result == json.loads(self.node_info)

    def test_convert_size_to_bytes(self, maas_storage):
        """Check if 'convert_size_to_bytes' correctly
        converts sizes from string format to byte values.
        """
        assert maas_storage.convert_size_to_bytes("1G") == 1000000000
        assert maas_storage.convert_size_to_bytes("500M") == 500000000
        assert maas_storage.convert_size_to_bytes("10K") == 10000
        assert maas_storage.convert_size_to_bytes("1000") == 1000

        with pytest.raises(MaasStorageError):
            maas_storage.convert_size_to_bytes("1Tb")
            maas_storage.convert_size_to_bytes("abc")

    def test_clear_storage_config(self, maas_storage):
        """Checks if 'clear_storage_config' correctly clears the
        storage configuration.
        """
        maas_storage.clear_storage_config()

        maas_storage.call_cmd_mock.assert_has_calls(
            [
                call(
                    [
                        "maas",
                        maas_storage.maas_user,
                        "partition",
                        "delete",
                        maas_storage.node_id,
                        "1",  # parent_block_id
                        "10",  # partition_id
                    ]
                ),
                call(
                    [
                        "maas",
                        maas_storage.maas_user,
                        "partition",
                        "delete",
                        maas_storage.node_id,
                        "2",
                        "20",
                    ]
                ),
                call(
                    [
                        "maas",
                        maas_storage.maas_user,
                        "block-device",
                        "unmount",
                        maas_storage.node_id,
                        "3",  # parent_block_id
                    ]
                ),
                call(
                    [
                        "maas",
                        maas_storage.maas_user,
                        "block-device",
                        "unformat",
                        maas_storage.node_id,
                        "3",  # parent_block_id
                    ]
                ),
            ]
        )

    def test_assign_parent_disk(self, maas_storage):
        """Checks if 'assign_parent_disk' correctly assigns a parent disk
        to a storage device.
        """
        maas_storage.device_list = [
            {"id": 1, "type": "disk"},
            {"id": 10, "type": "partition", "device": 1},
        ]

        maas_storage.assign_parent_disk()

        assert maas_storage.device_list == [
            {"id": 1, "type": "disk", "parent_disk": 1},
            {"id": 10, "type": "partition", "device": 1, "parent_disk": 1},
        ]

    def test_gather_partitions(self, maas_storage):
        """Checks if 'gather_partitions' correctly gathers partition sizes."""
        maas_storage.device_list = [
            {"id": 10, "type": "partition", "parent_disk": 1, "size": "500M"},
            {"id": 20, "type": "partition", "parent_disk": 1, "size": "1G"},
            {"id": 30, "type": "partition", "parent_disk": 2, "size": "2G"},
        ]

        maas_storage.gather_partitions()

        assert maas_storage.partition_sizes == {1: 1500000000, 2: 2000000000}

    def test_select_block_dev(self, maas_storage):
        """Checks if 'select_block_dev' correctly selects a block
        device based on id and size.
        """
        maas_storage.device_list = [
            {"id": 10, "type": "partition", "parent_disk": 1, "size": "500M"},
            {"id": 20, "type": "partition", "parent_disk": 1, "size": "1G"},
            {"id": 30, "type": "partition", "parent_disk": 2, "size": "2G"},
        ]

        block_device_id = maas_storage._select_block_dev(10, 1500000000)
        assert block_device_id == 1

        block_device_id = maas_storage._select_block_dev(20, 2000000000)
        assert block_device_id == 1

        with pytest.raises(MaasStorageError):
            maas_storage._select_block_dev(30, 50000000000000)

    def test_parse_block_devices(self, maas_storage):
        """Checks if 'parse_block_devices' correctly choses the most
        appropriate node block-id for the per-disk summed partition size.
        """
        maas_storage.partition_sizes = {
            1: 1500000000,
            2: 2000000000,
        }
        maas_storage.device_list = [
            {"id": 10, "type": "partition", "parent_disk": 1, "size": "500M"},
            {"id": 20, "type": "partition", "parent_disk": 1, "size": "1G"},
            {"id": 30, "type": "partition", "parent_disk": 2, "size": "2G"},
        ]

        maas_storage.block_ids = {}

        maas_storage.parse_block_devices()

        assert maas_storage.block_ids == {1: 1, 2: 2}

    def test_map_block_ids(self, maas_storage):
        """Checks if 'map_block_ids' correctly maps each partition to
        the appropriate block-device id.
        """
        maas_storage.block_ids = {1: 1, 2: 2, 3: 3}

        maas_storage.device_list = [
            {"id": 10, "type": "partition", "parent_disk": 1},
            {"id": 20, "type": "partition", "parent_disk": 2},
            {"id": 30, "type": "partition", "parent_disk": 3},
        ]

        maas_storage.map_block_ids()

        assert maas_storage.device_list == [
            {
                "id": 10,
                "type": "partition",
                "parent_disk": 1,
                "parent_disk_blkid": "1",
            },
            {
                "id": 20,
                "type": "partition",
                "parent_disk": 2,
                "parent_disk_blkid": "2",
            },
            {
                "id": 30,
                "type": "partition",
                "parent_disk": 3,
                "parent_disk_blkid": "3",
            },
        ]

    def test_validate_alloc_pct_values(self, maas_storage):
        """Checks if 'validate_alloc_pct_values' correctly validates total
        per-disk allocation percentages do not exceed 100.
        """
        maas_storage.device_list = [
            {"id": 10, "type": "partition", "parent_disk": 1, "alloc_pct": 50},
            {"id": 20, "type": "partition", "parent_disk": 1, "alloc_pct": 60},
            {"id": 30, "type": "partition", "parent_disk": 2, "alloc_pct": 90},
        ]

        with pytest.raises(MaasStorageError):
            maas_storage._validate_alloc_pct_values()

    def test_create_partition_sizes(self, maas_storage):
        """Checks if 'create_partition_sizes' correctly creates each partition
        based on the given parameters.
        """
        maas_storage.device_list = [
            {"id": 10, "type": "partition", "parent_disk": 1, "size": "1G"},
            {"id": 20, "type": "partition", "parent_disk": 2, "alloc_pct": 40},
            {"id": 30, "type": "partition", "parent_disk": 2, "alloc_pct": 60},
        ]
        maas_storage.block_ids = {1: 1, 2: 2}
        maas_storage.create_partition_sizes()

        assert maas_storage.device_list == [
            {
                "id": 10,
                "type": "partition",
                "parent_disk": 1,
                "size": 1000000000,
            },
            {
                "id": 20,
                "type": "partition",
                "parent_disk": 2,
                "alloc_pct": 40,
                "size": "160000000000",
            },
            {
                "id": 30,
                "type": "partition",
                "parent_disk": 2,
                "alloc_pct": 60,
                "size": "240000000000",
            },
        ]

    def test_group_by_type(self, maas_storage):
        """Checks if 'group_by_type' correctly groups each device by their
        storage device type, into a list per that type.
        """
        maas_storage.device_list = [
            {"id": 1, "type": "disk"},
            {"id": 10, "type": "partition"},
            {"id": 20, "type": "partition"},
            {"id": 40, "type": "format"},
            {"id": 50, "type": "format"},
            {"id": 60, "type": "mount"},
        ]

        result = maas_storage.group_by_type()

        assert result == {
            "disk": [{"id": 1, "type": "disk"}],
            "partition": [
                {"id": 10, "type": "partition"},
                {"id": 20, "type": "partition"},
            ],
            "format": [
                {"id": 40, "type": "format"},
                {"id": 50, "type": "format"},
            ],
            "mount": [{"id": 60, "type": "mount"}],
        }

    def test_process_by_dev_type(self, maas_storage):
        """Checks if 'process_by_dev_type' correctly batch-processes devices
        based on their type-grouping list.
        """
        devs_by_type = {
            "disk": [{"id": 1, "type": "disk"}],
            "partition": [{"id": 20, "type": "partition"}],
            "format": [{"id": 40, "type": "format"}],
            "mount": [{"id": 60, "type": "mount"}],
        }

        mock_methods = {
            "disk": "process_disk",
            "partition": "process_partition",
            "format": "process_format",
            "mount": "process_mount",
        }

        for dev_type, devices in devs_by_type.items():
            for device in devices:
                setattr(maas_storage, mock_methods[dev_type], MagicMock())

            setattr(
                maas_storage,
                f"_get_child_device_{dev_type}",
                MagicMock(return_value=devices),
            )

        maas_storage.process_by_dev_type(devs_by_type)

        for dev_type, devices in devs_by_type.items():
            for device in devices:
                mock_method = getattr(maas_storage, mock_methods[dev_type])
                mock_method.assert_called_once_with(device)

    def test_process_disk(self, maas_storage):
        """Checks if 'process_disk' correctly processes a 'disk'
        device type.
        """
        maas_storage.device_list = [
            {"id": 1, "type": "disk", "parent_disk": 1}
        ]
        device = {
            "id": 1,
            "type": "disk",
            "name": "sda",
            "parent_disk_blkid": 1,
        }

        maas_storage.process_disk(device)

        maas_storage.call_cmd_mock.assert_called_with(
            [
                "maas",
                maas_storage.maas_user,
                "block-device",
                "update",
                maas_storage.node_id,
                device["parent_disk_blkid"],
                f"name={device['name']}",
            ]
        )

    def test_process_partition(self, maas_storage):
        """Checks if 'process_partition' correctly processes a 'partition'
        device type.
        """
        device = {
            "id": 10,
            "type": "partition",
            "parent_disk": "sda",
            "parent_disk_blkid": 1,
            "size": "1G",
        }

        maas_storage._create_partition = MagicMock(return_value={"id": 3})

        maas_storage.process_partition(device)

        assert maas_storage._create_partition.call_args_list == [call(device)]

        assert device["partition_id"] == "3"

    def test_process_format(self, maas_storage):
        """Checks if 'process_format' correctly processes a 'format'
        device type.
        """
        device = {
            "id": 4,
            "type": "format",
            "fstype": "ext4",
            "label": "root",
            "parent_disk": 1,
            "parent_disk_blkid": "sda",
            "volume": "volume",
        }

        maas_storage._get_format_partition_id = MagicMock(return_value=2)

        maas_storage.process_format(device)

        maas_storage._get_format_partition_id.assert_called_with(
            device["volume"]
        )

        maas_storage.call_cmd_mock.assert_called_with(
            [
                "maas",
                maas_storage.maas_user,
                "partition",
                "format",
                maas_storage.node_id,
                device["parent_disk_blkid"],
                2,
                f"fstype={device['fstype']}",
                f"label={device['label']}",
            ]
        )

    def test_process_mount(self, maas_storage):
        """Checks if 'process_mount' correctly processes a 'mount'
        device type.
        """
        device = {
            "id": 6,
            "type": "mount",
            "path": "/mnt/data",
            "parent_disk": 1,
            "parent_disk_blkid": "sda",
            "device": "device",
        }

        maas_storage._get_mount_partition_id = MagicMock(return_value=2)

        maas_storage.process_mount(device)

        maas_storage._get_mount_partition_id.assert_called_with(
            device["device"]
        )

        maas_storage.call_cmd_mock.assert_called_with(
            [
                "maas",
                maas_storage.maas_user,
                "partition",
                "mount",
                maas_storage.node_id,
                device["parent_disk_blkid"],
                2,
                f"mount_point={device['path']}",
            ]
        )
