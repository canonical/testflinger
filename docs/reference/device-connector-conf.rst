Device connector configuration options
=======================================

The configuration of a device connector contains details that are unique to this device, such as the IP address and environment data that should be used when running tests on this device.

The device connector configuration is normally stored in a file called ``default.yaml`` in the source where the device connector runs.

The configuration options listed below are available for all device connectors unless otherwise specified. For the list of supported types of device connectors, see :doc:`device-connector-types`.

.. list-table:: Device connector configuration options
   :header-rows: 1    
  
   * - Field
     - Device connector type
     - Description
   * - ``agent_name``
     - all
     - Name of the device connector (short string, no spaces)
   * - ``device_ip``
     - all
     - IP address of the device used during provisioning
   * - ``reboot_script``
     - all 
     - List of commands that can be executed to hard reboot the device
   * - ``serial_host``
     - all 
     - (optional) ``ser2net`` host for capturing serial output
   * - ``serial_port``
     - all 
     - (optional) ``ser2net`` port for capturing serial output
   * - ``env``
     - all 
     - mapping of key value pairs of environment data that will be injected into the runtime environment on the agent host during the test phase
   * - ``testflinger_server``
     - multi
     - URL for the Testflinger server to connect to for creating subordinate test jobs used by a multi-job configuration
   * - ``maas_user``
     - maas
     - MAAS profile ID configured on the agent host to use for controlling the agent
   * - ``node_id``
     - maas
     - MAAS Node ID for the specific agent on the MAAS server associated with this test device
   * - ``reset_efi``
     - maas
     - Attempt to reset EFI systems to boot from the network in order to work around issues with the boot order sometimes getting lost on systems that require USB Ethernet dongles
   * - ``clear_tpm``
     - maas
     - Attempt to clear the TPM before provisioning the system, for SecureBoot systems
   * - ``timeout_min``
     - maas
     - Maximum time in minutes to wait for MAAS deployment to complete (default: 60)
   * - ``default_disks``
     - maas
     - Default disk storage configuration data for MAAS node storage layout
   * - ``snappy_writable_partition``
     - dragonboard
     - The writable partition for injecting the cloud-init user data for enabling a default user
   * - ``post_flash_cmds``
     - netboot
     - Netboot device connector specific steps needed after flashing the image that may be device-specific
   * - ``recovery_cmds``
     - oemrecovery
     - List of commands to execute that will trigger “recovery” on the specified device
   * - ``control_switch_device_cmd``
     - muxpi
     - Muxpi/SDWire command to execute to switch control of the SD card over to the test device so that it can boot the image
   * - ``control_switch_local_cmd``
     - muxpi
     - Muxpi/SDWire command to execute to switch control of the SD card over to the SD MUX controller so that it can flash an image
   * - ``post_provision_script``
     - muxpi
     - List of commands that must be executed on the test device after provisioning, with the test image mounted, for doing device-specific configuration
   * - ``control_host_reboot_script``
     - muxpi
     - List of commands to execute to reboot the control host before provisioning
   * - ``control_host_reboot_timeout``
     - muxpi
     - Time in seconds to wait after rebooting the control host (default: 120)
   * - ``control_host``
     - cm3, muxpi
     - IP of the sidecar device or “controller” that can be used to assist with provisioning. This device should already be configured for ssh using a key on the agent host.
   * - ``control_user``
     - cm3, muxpi
     - User to ssh to on the ``control_host`` (default: ``ubuntu``)
   * - ``test_device``
     - cm3, dragonboard, muxpi, netboot
     - Block device used for writing the test image. This device will be erased and overwritten with the requested image for provisioning.
   * - ``select_master_script``
     - dragonboard, netboot
     - List of commands used to force booting into the “stable” image that is used for provisioning the device
   * - ``select_test_script``
     - dragonboard, netboot
     - List of commands used to force booting into the “test” image once provisioning is complete

Example configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: yaml

  agent_name: rpi-example
  device_ip: <DEVICE_IP>
  control_host: <HOST_IP>
  test_device: /dev/sda
  serial_host: <HOST_IP>
  serial_port: <PORT>
  reboot_script:
  - snmpset -c private -v2c <IP> .1.3.6.1.4.1.13742.6.4.1.2.1.2.1.8 i 0
  - sleep 30
  - snmpset -c private -v2c <IP> .1.3.6.1.4.1.13742.6.4.1.2.1.2.1.8 i 1
  env:
    DEVICE_IP: <DEVICE_IP>
    WPA_AC_SSID: my-ac-ap
    WPA_AC_PSK: mypassword
    OTHER_DEVICE_DETAIL: foo
