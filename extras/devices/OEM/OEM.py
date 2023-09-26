"""Device classes for flashing firmware on device with OEM-specific methods"""

from devices.base import AbstractDevice


class OEMDevice(AbstractDevice):
    """Device class for devices that are not supported by LVFS-fwupd"""

    fw_update_type = "OEM-defined"

    def __init__(self, ipaddr: str, user: str, password: str):
        self.ipaddr = ipaddr
        self.user = user
        self.password = password
        self.fw_info = []
