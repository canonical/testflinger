MAAS Custom Storage Configuration
=================================
This extension of the Testflinger MAAS Testflinger Device Connector to handle a variety of node storage layout configurations. This configuration will be passed to Testflinger via the node job configuration YAML file, as part of the SUT provision data (example below). This functionality is contained in the discreet Python module (``maas-storage.py``) that sits alongside the MAAS Testflinger Device Connector, to be imported and called when this device connector is instantiated, if a storage layout configuration is supplied.

These storage layout configurations are to be passed along to MAAS, via the CLI API, when the device connector is created as part of its provision phase. While initial scope and use of this module will be limited to SQA testing requirements, the availability of this module implies additional consumers can specify disk layout configurations as part of their Testflinger job definitions.

Of note: the initial scope of storage to be supported will be limited to flat layouts and simple partitions;  RAID, LVM or ``bcache`` configurations are currently unsupported by this module. This functionality will be added in the future as the need arises.

Job Configuration
-----------------
The storage configuration is traditionally supplied as a node bucket config, so we can duplicate how this is laid out in the SUT job configuration at the end of this document.

As below, the storage configuration is defined under ``disks`` key in the YAML file. It is composed of a list of storage configuration entries, which are dictionaries with at least these two fields, ``type`` and ``id``:

-   **type**: the type of configuration entry. Currently this is one of:
	- ``disk`` - a physical disk on the system
	- ``partition`` - a partition on the system
	- ``format`` - instructions to format a volume
	- ``mount`` - instructions to mount a formatted partition
-   **id**: a label used to refer to this storage configuration entry. Other configuration entries will use this id to refer to this configuration item, or the component it configured.

Storage Types
-------------
Each type of storage configuration entry has additional fields of:

-   **Disk**: all storage configuration is ultimately applied to disks. These are referenced by ``disk`` storage configuration entries.
	- ``disk`` - The key of a disk in the machine's hardware configuration. By default, this is an integer value like ``0`` or ``1``.
	- ``ptable`` - Type of partition table to use for the disk (``gpt`` or ``msdos``).
	- ``name`` - Optional. If specified, the name to use for the disk, as opposed to the default one which is usually something like ``sda``. This will be used in ``/dev/disk/by-dname/`` for the disk and its partitions. So if you make the disk name ``rootdisk``, it will show up at <``/dev/disk/by-dname/rootdisk``>. This can be used to give predictable, meaningful names to disks, which can be referenced in Juju config, etc.
	- ``boot`` - Optional. If specified, this disk will be set as boot disk in MAAS.
	- The disk's ``id`` will be used to refer to this disk in other entries, such as ``partition``.
-   **Partition**: A partition of a disk is represented by a ``partition`` entry.
	- ``device`` - The ``id`` of the ``disk`` entry this partition should be created on.
	- ``number`` - Partition number.  This determines the order of the partitions on the disk.
	- ``size`` - The minimum required size of the partition, in bytes, or in larger units, given by suffixes (K, M, G, T)
	- The partition's ``id`` will be used to refer to this partition in other entries, such as ``format``.
	- ``alloc_pct`` - Percent (as an int) of the parent disk this partition should consume. This is optional, if this is not given, then the ``size`` value will be the created partition size. If multiple partitions exist on a parent disk, the total ``alloc_pct`` between them cannot exceed 100.
-   **Format**: Instructions to format a volume are represented by a ``format`` entry.
	- ``volume`` - the ``id`` of the entry to be formatted. This can be a disk or partition entry.
	- ``fstype`` - The file system type to format the volume with. See MAAS docs for options.
	- ``label`` - The label to use for the file system.
	- The format's ``id`` will be used to refer to this formatted volume in ``mount`` entries.
-   **Mount**: Instructions to mount a formatted volume are represented by a ``mount`` entry.
	- ``device`` - The ``id`` of the ``format`` entry this mount refers to.
	- ``path`` - The path to mount the formatted volume at, e.g. ``/boot``.

Storage Configuration Instantiation
-----------------------------------
-   The existing storage configuration on the SUT is first cleared in order to start with a clean slate.
-   We will then fetch the SUT block device config via the MAAS API in order to verify and choose the appropriate physical disks which exist on the system. These disks must align with the configuration parameters (size, number of disks) presented in the config to proceed.
-   Disk selection should be performed with the following criteria:
	- In instances where all disks meet the space requirements, we can numerically assign the lowest physical disk ID (in MAAS block-devices) to the first config disk. Subsequent disks will be assigned in numerical order.
	- In instances where the total of a config disk’s partition map (determined by adding all configuration partitions on that disk) will only fit on certain node disks, these disks will only be selected for the parent configuration disk of said partition map.
		- Disk selection will be done in numerical order as above within any smaller pool of disks that meet configuration partitioning criteria.
		- Node provisioning will fail if configuration partition maps exist that will not adequately fit on any disk, or if the pool of appropriate disks is exhausted prior to accommodating all configuration partition maps.
			- However, dynamic allocation of partition sizes using the ``alloc_pct`` field will enable a much more flexible allocation of partitions to parent disks, and one only needs to be able to provide the minimum partition size in order to select the most appropriate disk.
-   After disk selection takes place, all configuration elements of each storage type will be grouped together for batch processing. This order is determined by the dependency each type has on the other. The types and the order in which they will be processed will be: [``disk``, ``partition``, ``format``, ``mount``].
	- As additional storage types are supported in the future, this order will need to remain consistent with any parent-child relationship that exists between storage types.
-   The storage configuration will then be written to the node disks in this order.
	- If a boot partition exists in the configuration, the parent disk will be flagged as a boot disk via the MAAS API. The boot partition will then be created on this disk, including an EFI mount if desired.
-   After the storage configuration is completed and written to the node’s physical disks, node provisioning will proceed to OS installation, in addition to any other provisioning steps outside of the node’s storage subsystem.

Job Definition Reference
------------------------
..  code-block:: yaml
    :caption: job.yaml
    :linenos:

    disks:
    - id: disk0
      disk: 0
      type: disk
      ptable: gpt
    - id: disk0-part1
      device: disk0
      type: partition
      number: 1
      size: 2G
      alloc_pct: 80
    - id: disk0-part1-format
      type: format
      volume: disk0-part1
      fstype: ext4
      label: nova-ephemeral
    - id: disk0-part1-mount
      device: disk1-part1-format
      path: /
      type: mount
    - id: disk1
      disk: 1
      type: disk
      ptable: gpt
    - id: disk1-part1
      device: disk1
      type: partition
      number: 1
      size: 500M
      alloc_pct: 10
    - id: disk1-part1-format
      type: format
      volume: disk1-part1
      fstype: fat32
      label: efi
    - id: disk1-part1-mount
      device: disk1-part1-format
      path: /boot/efi
      type: mount
    - id: disk1-part2
      device: disk1
      type: partition
      number: 2
      size: 1G
      alloc_pct: 20
    - id: disk1-part2-format
      volume: disk1-part2
      type: format
      fstype: ext4
      label: boot
    - id: disk1-part2-mount
      device: disk1-part2-format
      path: /boot
      type: mount
    - id: disk1-part3
      device: disk1
      type: partition
      number: 3
      size: 10G
      alloc_pct: 60
    - id: disk1-part3-format
      volume: disk1-part3
      type: format
      fstype: ext4
      label: ceph
    - id: disk1-part3-mount
      device: disk1-part3-format
      path: /data
      type: mount
