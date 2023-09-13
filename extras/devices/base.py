"""Base class for flashing firmware on devices"""


import logging
from abc import ABC, abstractmethod

logger = logging


class AbstractDevice(ABC):
    fw_update_type = ""
    vendor = ""

    def __init__(self, ipaddr: str, user: str, password: str):
        self.ipaddr = ipaddr
        self.user = user
        self.password = password
        self.fw_info = []

    @abstractmethod
    def run_cmd(self):
        raise NotImplementedError("Please, implement the run_cmd method")

    @abstractmethod
    def get_fw_info(self):
        raise NotImplementedError("Please, implement the get_fw_info method")

    @abstractmethod
    def upgrade(self):
        raise NotImplementedError("Please, implement the upgrade method")

    @abstractmethod
    def downgrade(self):
        raise NotImplementedError("Please, implement the downgrade method")

    @abstractmethod
    def check_results(self):
        raise NotImplementedError("Please, implement the check_results method")

    @abstractmethod
    def check_connectable(self):
        raise NotImplementedError(
            "Please, implement the check_connectable method"
        )

    @abstractmethod
    def reboot(self):
        raise NotImplementedError("Please, implement the reboot method")
