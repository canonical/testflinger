from devices.base import AbstractDevice


class OEMDevice(AbstractDevice):
    fw_update_type = "OEM-defined"


class HPEDevice(OEMDevice):
    fw_update_type = "OEM-defined"
    vendor = "HPE"
