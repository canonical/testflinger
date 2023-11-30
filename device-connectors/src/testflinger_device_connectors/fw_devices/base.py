"""Base class for flashing firmware on devices"""

import time
import subprocess
import logging
from abc import ABC, abstractmethod
from testflinger_device_connectors import logmsg

SSH_OPTS = "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"


class AbstractDevice(ABC):
    fw_update_type = ""
    vendor = ""

    def __init__(self, ipaddr: str, user: str):
        self.ipaddr = ipaddr
        self.user = user
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
    def reboot(self):
        raise NotImplementedError("Please, implement the reboot method")

    def check_connectable(self, timeout: int):
        """
        After DUT reboot, check if SSH to DUT works within a given timeout
        period

        :param timeout: wait time for regaining DUT access
        """
        logmsg(
            logging.INFO,
            f"check and wait for {timeout}s until {self.ipaddr} is SSHable",
        )
        status = "1"
        timeout_start = time.time()

        while status != "0" and time.time() < timeout_start + timeout:
            try:
                status = subprocess.check_output(
                    f"ssh {SSH_OPTS} {self.user}@{self.ipaddr} "
                    + "/bin/true 2>/dev/null; echo $?",
                    shell=True,
                    universal_newlines=True,
                    timeout=10,
                ).strip()
            except (
                subprocess.TimeoutExpired,
                subprocess.CalledProcessError,
            ):
                pass
        if status != "0":
            err_msg = f"Failed to SSH to {self.ipaddr} after {timeout}s"
            logmsg(logging.ERROR, err_msg)
            raise RuntimeError(err_msg)
        delta = time.time() - timeout_start
        logmsg(logging.INFO, f"{self.ipaddr} is SSHable after {int(delta)}s")


class OEMDevice(AbstractDevice):
    """Device class for devices that are not supported by LVFS-fwupd"""

    fw_update_type = "OEM-defined"
