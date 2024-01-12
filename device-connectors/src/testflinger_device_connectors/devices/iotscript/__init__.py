"""OEM IoT provisioner support code."""

from testflinger_device_connectors.devices import DefaultDevice

device_name = "iotscript"


class DeviceConnector(DefaultDevice):
    def provision(self, args):
        pass
