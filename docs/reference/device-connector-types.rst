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
     - Uses `MaaS <https://maas.io/>`_ to provision supported images on devices that are capable of being controlled by a MaaS server.
   * - ``multi`` 
     - Experimental device type that is used for provisioning multiple other devices in order to coordinate a job across multiple devices at the same time.
   * - ``muxpi`` 
     - MuxPi or SDWire device capable of multiplexing the SD card so that it can be written, then control can be switched to the DUT to boot the image.
   * - ``netboot`` 
     - Special purpose device connector for a few devices that must be booted and flashed remotely but the image they need is not compatible with MaaS.
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
