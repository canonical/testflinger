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
     - Experimental device type that is used for provisioning multiple other devices in order to coordinate a job across multiple devices at the same time.
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
     - This device connector is used for OEM PC platforms starting from Ubuntu 24.04. It executes provision-image.sh script and consumes autoinstall configuration files to complete the installation.
   * - ``zapper_iot``
     - This device connector is used for provisioning ubuntu-core to ARM IoT devices. It could be provision by set device to download mode or override seed partition and do recovery.
   * - ``zapper_kvm``
     - This device connector makes use of Zapper KVM capabilities to install multiple types of Ubuntu images (vanilla, OEM, ...).

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
       ``unzstd`` (**xz** format is recommended, but any format supported by
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
       ``unzstd`` (**xz** format is recommended, but any format supported by
       the ``zstd`` tool is supported) and
       flashed to the SD card, which will be used to boot up the DUT.

.. _fake_connector:

fake_connector
--------------

The ``fake_connector`` device connector doesn't actually provision any devices, but is useful for testing the Testflinger without needing to have any real devices connected.

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
       `MAAS documentation: Set a specific kernel <https://maas.io/docs/how-to-customise-machines#set-a-specific-kernel-during-machine-deployment-5>`_.
       on this topic
   * - ``user_data``
     - A string containing base64 encoded cloud-init user data to be used for provisioning.
       For more information, see
       `MAAS documentation: Pre-seed cloud-init <https://maas.io/docs/how-to-customise-machines#pre-seed-cloud-init-2>`_.
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
       ``unzstd`` (**xz** format is recommended, but any format supported by
       the ``zstd`` tool is supported) and
       flashed to the SD card, which will be used to boot up the DUT.
   * - ``use_attachment``
     - If set, overrides the ``url`` above and uses :ref:`file attachments <file_attachments>`
       for deploying an image to the SD card.
   * - ``media``
     - Optional parameter to indicate on which boot media the disk image should
       be programmed (using zapper commands). Supported values are ``usb`` or 
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
        ``unzstd`` (**xz** format is recommended, but any format supported by
        the ``zstd`` tool is supported) and
        flashed to the device, which will be used to boot up the DUT.

.. _noprovision:

noprovision
-----------

The ``noprovision`` device connector does not support any ``provision_data`` keys.
However, you can specify any key in this dictionary (example: ``skip: false``) in
order to ensure the provision step is run. The only effect this will have, is to
ensure that the system is reachable with ssh before proceeding to the next step.

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

The ``dell_oemscript`` device connector does not support any ``provision_data`` keys.

.. list-table:: Supported ``provision_data`` keys for ``dell_oemscript``
   :header-rows: 1

   * - Key
     - Description
   * - ``url``
     - URL to a compressed disk image that is downloaded, decompressed using
       ``unzstd`` (**xz** format is recommended, but any format supported by
       the ``zstd`` tool is supported) and
       flashed to the device, which will be used to boot up the DUT.

.. _lenovo_oemscript:

lenovo_oemscript
----------------

The ``lenovo_oemscript`` device connector does not support any ``provision_data`` keys.

.. list-table:: Supported ``provision_data`` keys for ``lenovo_oemscript``
   :header-rows: 1

   * - Key
     - Description
   * - ``url``
     - URL to a compressed disk image that is downloaded, decompressed using
       ``unzstd`` (**xz** format is recommended, but any format supported by
       the ``zstd`` tool is supported) and
       flashed to the device, which will be used to boot up the DUT.

.. _hp_oemscript:

hp_oemscript
------------

The ``hp_oemscript`` device connector does not support any ``provision_data`` keys.

.. list-table:: Supported ``provision_data`` keys for ``hp_oemscript``
   :header-rows: 1

   * - Key
     - Description
   * - ``url``
     - URL to a compressed disk image that is downloaded, decompressed using
       ``unzstd`` (**xz** format is recommended, but any format supported by
       the ``zstd`` tool is supported) and
       flashed to the device, which will be used to boot up the DUT.

.. _oem_autoinstall:

oem_autoinstall
------------

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

    * - ``user_data``
      - Required file provided with :ref:`file attachments <file_attachments>`.
        This file will be consumed by the autoinstall and cloud-init.
        Sample user-data is provided in the section below.
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

.. _zapper_kvm:

zapper_kvm
------------

The ``zapper_kvm`` device connector, depending on the target image, supports the following ``provision_data`` keys:

.. list-table:: Supported ``provision_data`` keys for ``zapper_kvm`` with target autoinstall-driven provisioning
    :header-rows: 1

    * - Key
      - Description
    * - ``url``
      - URL to a disk image that is downloaded and flashed to a USB storage device,
        which will be used to boot up the DUT.
    * - ``robot_tasks``
      - List of Zapper/Robot snippets to run in sequence after the USB storage device
        is plugged into the DUT and the system restarted. The snippet ID is the relative
        path from the ``robot/snippets`` path in the Zapper repository.
    * - ``autoinstall_storage_layout``
      - When provisioning an image supporting *autoinstall*, the storage_layout can
        be either ``lvm`` (default), ``direct``, ``zfs`` or ``hybrid`` (Desktop 23.10+, UC24)
    * - ``cmdline_append``
      - (Optional) When provisioning an image supporting *autoinstall*, the cmdline_append can
        be used to append Kernel parameters to the standard GRUB entry.
    * - ``autoinstall_base_user_data``
      - (Optional) A string containing base64 encoded user-data to use as base for autoinstall-driven provisioning.
        For more information, see
        `Autoinstall Reference <https://canonical-subiquity.readthedocs-hosted.com/en/latest/reference/autoinstall-reference.html>`_.
        on this topic
    * - ``autoinstall_oem``:
      - (Optional) Set to "true" to install OEM meta-packages and the reset partition (Desktop 24.04+).
    * - ``ubuntu_sso_email``:
      - (Optional) A valid Ubuntu SSO email to which the DUT provisioned with a non-dangerous grade UC image will be linked (UC24). Please make sure to provide the corresponding *username* in the *test_data.test_username* field.
.

.. list-table:: Supported ``provision_data`` keys for ``zapper_kvm`` with target Ubuntu OEM 22.04
    :header-rows: 1

    * - Key
      - Description
    * - ``alloem_url``
      - URL to the ``alloem`` disk image that is downloaded and flashed to a USB storage device,
        which will be used to boot up the DUT. It restores the OEM reset partition and installs
        a base Ubuntu OEM 22.04 image.
    * - ``robot_tasks``
      - List of Zapper/Robot snippets to run in sequence after the USB storage device
        is plugged into the DUT and the system restarted. The snippet ID is the relative
        path from the ``robot/snippets`` path in the Zapper repository.
    * - ``url``
      - Optional URL to a disk image given as input to the ``oemscript`` to install on top of
        the base OEM provisioning.
    * - ``oem``
      - Optional value to select the ``oemscript`` to run when specifying a ``url``, possible values
        are ``dell``, ``hp`` and ``lenovo``.

.. list-table:: Supported ``provision_data`` keys for ``zapper_kvm`` with target any generic live ISOs
    :header-rows: 1

    * - Key
      - Description
    * - ``url``
      - URL to a disk image that is downloaded and flashed to a USB storage device,
        which the DUT will then boot from.
    * - ``robot_tasks``
      - List of Robot snippets to run in sequence after the USB storage device
        is plugged into the DUT and the system restarted. The snippet ID is the relative
        path from the ``robot/snippets`` path in the Zapper repository.
    * - ``live_image``
      - Set to "true" to ensure that the Zapper considers the provision process complete at the end of KVM interactions defined by the specified `robot_tasks`, without needing to unplug the external media.
    * - ``wait_until_ssh``
      - If set to "false", the Zapper will skip the SSH connection attempt, which is normally performed at the end of provisioning as a form of boot assertion. This is primarily useful in cases where the live ISO does not include an SSH server.
