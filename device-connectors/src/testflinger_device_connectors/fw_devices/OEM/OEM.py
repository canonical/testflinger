"""Device classes for flashing firmware on device with OEM-specific methods"""

from testflinger_device_connectors.fw_devices.base import AbstractDevice


class OEMDevice(AbstractDevice):
    """Device class for devices that are not supported by LVFS-fwupd"""

    fw_update_type = "OEM-defined"


class HPEDevice(OEMDevice):
    """Place-holder for device class for HPE server"""

    fw_update_type = "OEM-defined"
    vendor = "HPE"
