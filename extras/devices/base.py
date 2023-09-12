import logging
from abc import ABC, abstractmethod

logger = logging


class AbstractDevice(ABC):
    fw_update_type = ""
    vendor = ""

    def __init__(self, ipaddr, user, password):
        self.ipaddr = ipaddr
        self.user = user
        self.password = password
        self.fw_info = []

    @abstractmethod
    def run_cmd(self):
        return NotImplemented

    @abstractmethod
    def get_fw_info(self):
        return NotImplemented

    @abstractmethod
    def upgrade(self):
        return NotImplemented

    @abstractmethod
    def downgrade(self):
        return NotImplemented

    @abstractmethod
    def check_results(self):
        return NotImplemented

    @abstractmethod
    def check_connectable(self):
        return NotImplemented

    @abstractmethod
    def reboot(self):
        return NotImplemented
