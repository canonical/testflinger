Supported device connector types
=================================

The following device connector types are currently supported. Note that with the exception of ``noprovision`` and ``maas2``, most of these device connectors require special hardware and/or configuration that is specific to our lab environment. However, the intent is that device connectors can be written to contain any amount of special handling necessary to handle any site-specific requirements.
 
To specify the commands to run by the device in each test phase, set the ``testflinger-device-connector`` command in the :doc:`Testflinger agent host configuration file <testflinger-agent-conf>` for each device connector. You can optionally configure each command to be called with different parameters or using containers.

.. list-table:: Supported device connector types
   :header-rows: 1

   * - Device connector type
     - Description
   * - ``cm3`` 
     - Raspberry Pi Compute modules. This requires a sidecar device, along with some custom cabling and software to handle putting the cm3 into a mode where it can be provisioned, then booting it.
   * - ``dragonboard`` 
     - Qualcomm Dragonboard 410c setup to boot from both a special image on a USB stick when the SD card is erased, as well as an SD card that can be provisioned by booting the stable image on a USB stick and then flashing the new image to the SD card.
   * - ``maas2`` 
     - Uses `MAAS <https://maas.io/>`_ to provision supported images on devices that are capable of being controlled by a MAAS server.
   * - ``multi``
     - Device connector for coordinating multi-device jobs. Provisions multiple devices simultaneously and optionally reserves them for SSH access. Supports credential inheritance, allowing child jobs to inherit authentication permissions from the parent job. See :doc:`../how-to/multi-device-jobs` for detailed usage.
   * - ``muxpi`` 
     - MuxPi or SDWire device capable of multiplexing the SD card so that it can be written, then control can be switched to the DUT to boot the image, see :ref:`muxpi`.
   * - ``netboot`` 
     - Special purpose device connector for a few devices that must be booted and flashed remotely but the image they need is not compatible with MAAS.
   * - ``noprovision`` 
     - General device connector that does not support provisioning, but can run tests on a device where provisioning is not needed or not possible to do automatically.
   * - ``oemrecovery`` 
     - device connector where provisioning involves triggering a “recovery” mode to reset the image back to its original state.  This is useful for things like Ubuntu Core images with full disk encryption, which can be preloaded with cloud-init data to ensure user creation, then a command is configured for the device connector that will cause it to be reset back to its original state.
   * - ``dell_oemscript``
     - This device connector is used for Dell OEM devices running certain versions of OEM supported images that can use a recovery partition to recover not only the same image, but in some cases, other OEM image versions as well.
   * - ``lenovo_oemscript`` 
     - This device connector is used for Lenovo OEM devices running certain versions of OEM supported images that can use a recovery partition to recover not only the same image, but in some cases, other OEM image versions as well.
   * - ``hp_oemscript`` 
     - This device connector is used for HP OEM devices running certain versions of OEM supported images that can use a recovery partition to recover not only the same image, but in some cases, other OEM image versions as well.
   * - ``oem_autoinstall``
     - This device connector is used for HP/Dell/Lenovo OEM PC platforms starting from Ubuntu 24.04 and supports only OEM images (not Stock Ubuntu). It executes provision-image.sh script and consumes autoinstall configuration files to complete the installation.

.. _cm3:

cm3
---

The ``cm3`` device connector supports the following ``provision_data`` keys:

.. list-table:: Supported ``provision_data`` keys for ``cm3``
   :header-rows: 1

   * - Key
     - Description
   * - ``url``
     - URL to a compressed disk image that is downloaded, decompressed using
       ``unzstd`` (``xz`` format is recommended, but any format supported by
       the ``zstd`` tool is supported) and
       flashed to the device, which will be used to boot up the DUT.

.. _dragonboard:

dragonboard
-----------

The ``dragonboard`` device connector supports the following ``provision_data`` keys:

.. list-table:: Supported ``provision_data`` keys for ``dragonboard``
   :header-rows: 1

   * - Key
     - Description
   * - ``url``
     - URL to a compressed disk image that is downloaded, decompressed using
       ``unzstd`` (``xz`` format is recommended, but any format supported by
       the ``zstd`` tool is supported) and
       flashed to the SD card, which will be used to boot up the DUT.

.. _fake_connector:

fake_connector
--------------

The ``fake_connector`` device connector doesn't actually provision any devices, but is useful for testing the Testflinger without needing to have any real devices connected.

.. _multi:

multi
-----

The ``multi`` device connector is used for coordinating multi-device jobs across multiple devices simultaneously. It creates child jobs for each device, waits for them to be allocated, and optionally reserves them for SSH access.

**Workflow:**

1. **Provision phase**: Creates and submits child jobs via the ``/v1/agent/jobs`` endpoint with credential inheritance
2. **Allocate phase**: Waits for all child jobs to reach ``allocated`` state
3. **Reserve phase** (optional): Copies SSH keys to all allocated devices
4. **Test phase** (optional): Executes coordinated tests across devices
5. **Cleanup phase**: Cancels all child jobs

The ``multi`` device connector supports the following ``provision_data`` keys:

.. list-table:: Supported ``provision_data`` keys for ``multi``
   :header-rows: 1

   * - Key
     - Description
   * - ``jobs``
     - List of child job definitions. Each entry must contain:

       - ``job_queue``: Queue name for the child device
       - ``provision_data``: Device-specific provisioning parameters (varies by device connector type)

The ``multi`` device connector supports the following ``reserve_data`` keys:

.. list-table:: Supported ``reserve_data`` keys for ``multi``
   :header-rows: 1

   * - Key
     - Description
   * - ``ssh_keys``
     - List of SSH key identifiers to import and copy to all devices. Format: ``provider:username`` (e.g., ``gh:username`` for GitHub or ``lp:username`` for Launchpad). Uses ``ssh-import-id`` to retrieve keys.
   * - ``timeout``
     - Reservation duration in seconds. Default: 3600 (1 hour). Can also use duration format (e.g., ``2h30m``). This timeout is independent from ``global_timeout``.

**Additional fields:**

- ``allocation_timeout``: Maximum time (in seconds) to wait for all child jobs to reach allocated state. Default: 7200 (2 hours)
- ``test_data.test_username``: SSH username for device connections. Default: ``ubuntu``

**Credential inheritance:**

Child jobs automatically inherit authentication permissions (``auth_permissions``) from the parent job, including:

- Extended reservation time limits (``max_reservation_time``)
- Job priority settings (``max_priority``)
- Restricted queue access (``allowed_queues``)

This enables authenticated users to submit multi-device jobs with elevated privileges that apply to all child jobs.

**Example:**

.. code-block:: yaml

  job_queue: multi
  allocation_timeout: 7200
  provision_data:
    jobs:
      - job_queue: rpi4b
        provision_data:
          url: https://cdimage.ubuntu.com/ubuntu-core/22/stable/current/ubuntu-core-22-arm64+raspi.img.xz
      - job_queue: maas-x86
        provision_data:
          distro: jammy
  reserve_data:
    ssh_keys:
      - "gh:your-username"
    timeout: "3600"
  test_data:
    test_username: ubuntu
    test_cmds: |
      # Access device IPs from job_list.json
      jq '.[].device_info.device_ip' job_list.json

For comprehensive documentation on multi-device jobs, see :doc:`../how-to/multi-device-jobs`.

.. _maas2:

maas2
-----

The ``maas2`` device connector supports the following ``provision_data`` keys:

.. list-table:: Supported ``provision_data`` keys for ``maas2``
   :header-rows: 1

   * - Key
     - Description
   * - ``distro``
     - Name of the image to be used for provisioning. This is the name of the
       image as it appears in the MAAS web UI and must already be imported into MAAS.
   * - ``kernel``
     - Specify a kernel to use during deployment. This is the name of the
       kernel as it appears in the MAAS web UI and must already be imported into MAAS.
       For more information, see
       `MAAS documentation: Set a specific kernel <https://maas.io/docs/about-machine-customization#p-17465-custom-ubuntu-kernels>`_.
       on this topic
   * - ``user_data``
     - A string containing base64 encoded cloud-init user data to be used for provisioning.
       For more information, see
       `MAAS documentation: Pre-seed cloud-init <https://maas.io/docs/about-machine-customization#p-17465-pre-seeding>`_.
       on this topic
   * - ``disks``
     - Specify a custom disk configuration for the machine. For more information, see the
       :doc:`maas_storage`.


.. _muxpi:

muxpi
-----

The ``muxpi`` device connector supports the following ``provision_data`` keys:

.. list-table:: Supported ``provision_data`` keys for ``muxpi``
   :header-rows: 1

   * - Key
     - Description
   * - ``url``
     - URL to a compressed disk image that is downloaded, decompressed using
       ``unzstd`` (``xz`` format is recommended, but any format supported by
       the ``zstd`` tool is supported) and
       flashed to the SD card, which will be used to boot up the DUT.
   * - ``use_attachment``
     - If set, overrides the ``url`` above and uses :ref:`file attachments <file_attachments>`
       for deploying an image to the SD card.
   * - ``media``
     - Optional parameter to indicate on which boot media the disk image should
       be programmed. Supported values are ``usb`` or 
       ``sd``
   * - ``create_user``
     - Boolean (default ``true``) specifying whether a user account should be created.
   * - ``boot_check_url``
     - URL to use for checking if the DUT has finished booting; a literal
       ``$DEVICE_IP`` in the URL will be replaced with the IP address of the DUT.
       Requesting the URL has to return HTTP status code 200 for the device to
       be considered "booted".
       If not set, SSH will be used to check when the device comes online.
       When ``boot_check_url`` is set, the SSH key for public key authentication
       won't be installed on the DUT to allow for test cases without SSH.

Image types recognised for user account creation
(the device type is not used if ``create_user: false`` is set in ``provision_data``):

.. list-table:: Supported image types
   :header-rows: 1

   * - Image type
     - Description
   * - ``ce-oem-iot``
     - IoT OEM certification
   * - ``tegra``
     - NVidia Tegra
   * - ``pi-desktop``
     - Ubuntu Desktop on Raspberry Pi
   * - ``ubuntu``
     - Ubuntu Classic
   * - ``core``
     - Ubuntu Core
   * - ``core20``
     - Ubuntu Core 20
   * - ``ubuntu-cpc``
     - Ubuntu Certified Public Cloud

.. _netboot:

netboot
-------

The ``netboot`` device connector supports the following ``provision_data`` keys:

.. list-table:: Supported ``provision_data`` keys for ``netboot``
    :header-rows: 1
  
    * - Key
      - Description
    * - ``url``
      - URL to a compressed disk image that is downloaded, decompressed using
        ``unzstd`` (``xz`` format is recommended, but any format supported by
        the ``zstd`` tool is supported) and
        flashed to the device, which will be used to boot up the DUT.

.. _noprovision:

noprovision
-----------

The ``noprovision`` device connector supports the following ``provision_data`` keys:

.. list-table:: Supported ``provision_data`` keys for ``noprovision``
   :header-rows: 1

   * - Key
     - Description
   * - ``skip``
     - If set to ``false``, the provision step will not be skipped. This will
       have the effect of ensuring that the system is reachable with ssh
       before proceeding to the next step.

.. _oemrecovery:

oemrecovery
-----------

The ``oemrecovery`` device connector does not support any ``provision_data`` keys.
Instead, this device connector uses a preconfigured command to reset the device back
to its original state. In order to ensure that the provision step is run, and the
system is reset back to the original state, you can specify any key in this dictionary
(example: ``skip: false``). If you do not want the provision step to run, you can
simply leave out the ``provision_data`` section.

.. _dell_oemscript:

dell_oemscript
--------------

The ``dell_oemscript`` device connector supports the following ``provision_data`` keys.

.. list-table:: Supported ``provision_data`` keys for ``dell_oemscript``
   :header-rows: 1

   * - Key
     - Description
   * - ``url``
     - URL to a compressed disk image that is downloaded, decompressed using
       ``unzstd`` (``xz`` format is recommended, but any format supported by
       the ``zstd`` tool is supported) and
       flashed to the device, which will be used to boot up the DUT. The image
       must be an OEM Image that retains a recovery partition on the machine.

.. _lenovo_oemscript:

lenovo_oemscript
----------------

The ``lenovo_oemscript`` device connector supports the following ``provision_data`` keys.

.. list-table:: Supported ``provision_data`` keys for ``lenovo_oemscript``
   :header-rows: 1

   * - Key
     - Description
   * - ``url``
     - URL to a compressed disk image that is downloaded, decompressed using
       ``unzstd`` (``xz`` format is recommended, but any format supported by
       the ``zstd`` tool is supported) and
       flashed to the device, which will be used to boot up the DUT. The image
       must be an OEM Image that retains a recovery partition on the machine.

.. _hp_oemscript:

hp_oemscript
------------

The ``hp_oemscript`` device connector supports the following ``provision_data`` keys.

.. list-table:: Supported ``provision_data`` keys for ``hp_oemscript``
   :header-rows: 1

   * - Key
     - Description
   * - ``url``
     - URL to a compressed disk image that is downloaded, decompressed using
       ``unzstd`` (``xz`` format is recommended, but any format supported by
       the ``zstd`` tool is supported) and
       flashed to the device, which will be used to boot up the DUT. The image
       must be an OEM Image that retains a recovery partition on the machine.

.. _oem_autoinstall:

oem_autoinstall
---------------

The ``oem_autoinstall`` device connector supports the following ``provision_data`` keys.

.. list-table:: Supported ``autoinstall`` keys for ``user_data`` config file
    :header-rows: 1

    * - Key
      - Description
    * - ``url``
      - URL to the image file which will be used to provision the device.
    * - ``token_file``
      - Optional credentials file in :ref:`file attachments <file_attachments>` when ``url``
        requires authentication. These credentials will be used with HTTPBasicAuth
        to download the image from ``url``. It must contain:

          username: $MY_USERNAME

          token: $MY_TOKEN

        If ``url`` requires webdav authentication, then device will use rclone to copy the file.
        The rclone configurations must be provided in the following format:

          [$PROJECT]

          type = webdav

          url = $URL

          vendor = other

          user = $USER

          pass = $PASSWORD

    * - ``user_data``
      - Optional file provided with :ref:`file attachments <file_attachments>`.
        This file will be consumed by the autoinstall and cloud-init.
        Sample user-data is provided in the section below. When file is missing
        connector will use the default-user-data file.
    * - ``redeploy_cfg``
      - Optional file provided with :ref:`file attachments <file_attachments>`.
        This file will override the grub.cfg in reset partition.
        By default, boots the DUT from reset partition to start the provisioning.
    * - ``authorized_keys``
      - Optional file provided with :ref:`file attachments <file_attachments>`.
        It will be copied to /etc/ssh/ on provisioned device and allows to import
        keys in bulk when system does not have internet access for ssh-import-id.
        The keys listed in this file are allowed to access the system in addition
        to keys in ~/.ssh/authorized_keys.

Sample cloud-config file for ``user_data`` key. It should contain directives for
autoinstall and cloud-init. Following is the basic structure example with explanations.
Optional packages, keys, users, or commands can be added to customise the installation.

For more details, please refer to
`Autoinstall Reference <https://canonical-subiquity.readthedocs-hosted.com/en/latest/reference/autoinstall-reference.html>`_
on this topic

  .. code-block:: bash

    #cloud-config
    # vim: syntax=yaml

    autoinstall:  # autoinstall configuration for the installer (subiquity)
      version: 1

      storage:
        layout:
          name: direct
          match:
            install-media: true

      early-commands:
        - "nmcli networking off"  # prevents online updating packages in subiquity installer

      late-commands:
        # hook.sh is a part of OEM image scripts
        - "bash /cdrom/sideloads/hook.sh late-commands"
        - "mount -o rw,remount /cdrom"

      # Copy /cdrom/ssh-config to /target/etc/ssh, if it exists.
      # File provided in authorized_keys key is copied here.
      - "! [ -d /cdrom/ssh-config ] || ( mkdir -p /target/etc/ssh && \
          cp -r /cdrom/ssh-config/* /target/etc/ssh)"
      shutdown: reboot  # tell the installer to reboot after installation

      # cloud-init config for the provisioned system
      user-data:
        bootcmd:
          - "bash /sp-bootstrap/hook.sh early-welcome"
        users:
          - default
        packages:  # list of packages to be installed
          - openssh-server
        runcmd:
          # set default ubuntu user and unlock password login
          - ["usermod", "-p", "MY_PASSWORD", "ubuntu"]
          - ["passwd", "-u", "ubuntu"]

        # key to be added in ~/.ssh/authorized_keys
        ssh_authorized_keys:
          - 'ssh-rsa MY_PUBLIC_KEY user@host'

        # Reboot after early-welcome is done
        power_state:
          mode: "reboot"
          message: "early-welcome setup complete, rebooting..."
          timeout: 30

    bootcmd:  # bootcmd of autoinstall
      - ['plymouth', 'display-message', '--text', 'Starting installer...']
