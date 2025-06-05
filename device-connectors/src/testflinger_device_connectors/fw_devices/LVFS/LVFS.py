"""Device class for flashing firmware on device supported by LVFS-fwupd."""

import json
import logging
import subprocess
import time
from enum import Enum, auto
from typing import Tuple

from testflinger_device_connectors.fw_devices.base import (
    SSH_OPTS,
    AbstractDevice,
    FirmwareUpdateError,
)

logger = logging.getLogger(__name__)


class LVFSDevice(AbstractDevice):
    """Device class for devices supported by LVFS-fwupd."""

    fw_update_type = "LVFS"
    vendor = ["HP", "Dell Inc.", "LENOVO"]
    reboot_timeout = 900

    def run_cmd(
        self, cmd: str, raise_stderr: bool = True, timeout: int = 30
    ) -> Tuple[int, str, str]:
        """Execute command on the DUT via SSH.

        :param cmd:          command to run on the DUT
        :param raise_stderr: when set to `True`, raise RuntimeError if return
                             code != 0, otherwise ignore it
        :param timeout:      timeout for the command response
        :returns:            return code, stdout, stderr
        """
        ssh_cmd = f'ssh -t {SSH_OPTS} {self.user}@{self.ipaddr} "{cmd}"'
        try:
            r = subprocess.run(
                ssh_cmd,
                shell=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            if raise_stderr:
                raise FirmwareUpdateError(e.output) from e
            else:
                return 124, f"command timeout after {timeout}s", ""
        rc, stdout, stderr = (
            r.returncode,
            r.stdout.decode().strip(),
            r.stderr.decode().strip(),
        )
        if raise_stderr and rc != 0:
            err_msg = f"Failed to execute {cmd}:\n [{rc}] {stdout} {stderr}"
            raise FirmwareUpdateError(err_msg)
        return rc, stdout, stderr

    def get_fw_info(self):
        """Get current firmware version of all updatable devices on DUT, and
        print out devices with upgradable/downgradable versions.
        """
        self._install_fwupd()
        logger.info("collect firmware info")
        self.run_cmd("sudo fwupdmgr refresh --force")
        rc, stdout, stderr = self.run_cmd("sudo fwupdmgr get-devices --json")
        logger.info("output of '$fwupdmgr get-devices'\n%s", stdout)
        self._parse_fwupd_raw(stdout)

    def _install_fwupd(self):
        self.run_cmd("sudo apt update", raise_stderr=False, timeout=120)
        self.run_cmd("sudo apt install -y fwupd")
        rc, stdout, stderr = self.run_cmd("sudo fwupdmgr --version")
        logger.info("fwupd version\n%s", stdout)

    def _parse_fwupd_raw(self, fwupd_raw: str) -> bool:
        """Parse the output of ```$ fwupdmgr get-devices```.

        :param fwupd_raw: output string of ```$ fwupdmgr get-devices```
        """
        for dev in json.loads(fwupd_raw)["Devices"]:
            if "Flags" in dev and "updatable" in dev["Flags"]:
                self.fw_info.append(dev)

        for dev in self.fw_info:
            if "Version" in dev:
                dev_name = dev["Name"] if "Name" in dev else dev["DeviceId"]
                msg = f"[{dev_name}] current version: {dev['Version']}"
            else:
                msg = ""
            if "Releases" in dev:
                higher_ver, lower_ver, same_ver = [], [], []
                vers = ""
                for rel in dev["Releases"]:
                    if "Flags" not in rel:
                        continue
                    elif "is-upgrade" in rel["Flags"]:
                        higher_ver.append(rel["Version"])
                    elif "is-downgrade" in rel["Flags"]:
                        lower_ver.append(rel["Version"])
                    else:
                        same_ver.append(rel["Version"])
                if higher_ver != []:
                    vers = (
                        " - LVFS upgradable version(s): "
                        + f"{', '.join(higher_ver)}"
                    )
                if lower_ver != []:
                    vers += (
                        " - LVFS downgradable version(s): "
                        + f"{', '.join(lower_ver)}"
                    )
                if vers:
                    msg += vers
            else:
                msg += " - no available firmware on LVFS"
            if msg:
                logger.info(msg)

    def upgrade(self) -> bool:
        """Upgrade all devices firmware to latest version if available on LVFS.

        :return: `True` if upgrading is done and reboot is required, `False`
                 otherwise
        """
        logger.info("start upgrading")
        reboot = False
        for dev in self.fw_info:
            dev_name = dev["Name"] if "Name" in dev else dev["DeviceId"]
            try:
                latest_ver = dev["Releases"][0]
            except KeyError:
                continue
            if dev["Version"] != latest_ver["Version"]:
                if "is-upgrade" in latest_ver["Flags"]:
                    logger.info(
                        "[%s] try upgrading to %s",
                        dev_name,
                        latest_ver["Version"],
                    )
                    dev["targetVersion"] = latest_ver["Version"]
                    rc, stdout, stderr = self.run_cmd(
                        f"sudo fwupdmgr upgrade {dev['DeviceId']} "
                        + "-y --no-reboot-check",
                        raise_stderr=False,
                    )
                    if rc == 0:
                        reboot = True
                    else:
                        logger.error(
                            "[%s] Failed to upgrade to %s\nerror: %s",
                            dev_name,
                            latest_ver["Version"],
                            stdout,
                        )
                else:
                    logger.info("[%s] not an upgradable component", dev_name)
            else:
                logger.info(
                    "[%s] already the latest available firmware version",
                    dev_name,
                )
        return reboot

    def downgrade(self) -> bool:
        """Downgrade all devices firmware to 2nd new version
        if available on LVFS.

        :return: `True` if downgrading is done and reboot is required, `False`
                 otherwise
        """
        logger.info("start downgrading")
        reboot = False
        for dev in self.fw_info:
            dev_name = dev["Name"] if "Name" in dev else dev["DeviceId"]
            try:
                prev_ver = dev["Releases"][1]
            except (KeyError, IndexError):
                continue
            if dev["Version"] == prev_ver["Version"]:
                logger.info("[%s] already the previous version", dev_name)
                continue
            if "is-downgrade" in prev_ver["Flags"]:
                dev["targetVersion"] = prev_ver["Version"]
                fw_file = prev_ver["Uri"].split("/")[-1]
                logger.info(
                    "[%s] try downgrading to %s", dev_name, prev_ver["Version"]
                )
                rc, stdout, stderr = self.run_cmd(
                    f"sudo fwupdmgr download {prev_ver['Uri']}",
                    raise_stderr=False,
                )
                if not (rc == 0 or (rc == 1 and "already exists" in stderr)):
                    raise FirmwareUpdateError(
                        f"[{dev_name}] fail to download firmware file from"
                        f" LVFS target: {prev_ver['Uri']}\nerror: {stdout}"
                    )
                rc, stdout, stderr = self.run_cmd(
                    f"sudo fwupdmgr install {fw_file} -y "
                    + "--no-reboot-check --allow-older",
                    raise_stderr=False,
                )
                if rc == 0:
                    reboot = True
                else:
                    logger.error(
                        (
                            "[%s] fail to force install (downgrade) "
                            "firmware %s\nerror: %s"
                        ),
                        dev_name,
                        fw_file,
                        stdout,
                    )
            else:
                logger.info("[%s] not a downgradable component", dev_name)
        return reboot

    def check_results(self) -> bool:
        """Get upgrade/downgrade result and validate if it succeeds.

        :return: `True` if overall upgrade status is success, `False` otherwise
        """
        fwupd_result = True
        for dev in self.fw_info:
            try:
                dev_name = dev["Name"]
            except KeyError:
                dev_name = dev["DeviceId"]
            try:
                expected_ver = dev["targetVersion"]
            except KeyError:
                continue
            rc, stdout, stderr = self.run_cmd(
                f"sudo fwupdmgr get-results {dev['DeviceId']} --json"
            )
            get_results = json.loads(stdout)
            try:
                new_fw = get_results["Releases"][0]
                update_state = get_results["UpdateState"]
            except KeyError:
                logger.error(
                    (
                        "[%s] unable to determine if new firmware is landed "
                        "due to missing results"
                    ),
                    dev_name,
                )
                fwupd_result = False
                continue

            if (
                new_fw["Version"] == expected_ver
                and update_state
                == FwupdUpdateState.FWUPD_UPDATE_STATE_SUCCESS.value
            ):
                logger.info(
                    "[%s] firmware flashed %s → %s",
                    dev_name,
                    dev["Version"],
                    expected_ver,
                )
            else:
                update_err = get_results.get("UpdateError", "")
                logger.error(
                    "[%s] %s: %s",
                    dev_name,
                    FwupdUpdateState(update_state).name,
                    update_err,
                )
                fwupd_result = False

        return fwupd_result

    def check_connectable(self, timeout: int):
        """After DUT reboot, check if SSH to DUT works within a given timeout
        period.

        :param timeout: wait time for regaining DUT access
        """
        logger.info(
            "check and wait for %ss until %s is SSHable", timeout, self.ipaddr
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
            logger.error(err_msg)
            raise FirmwareUpdateError(err_msg)
        delta = time.time() - timeout_start
        logger.info("%s is SSHable after %ds", self.ipaddr, int(delta))

    def reboot(self):
        """Reboot the DUT from OS."""
        logger.info("reboot DUT")
        self.run_cmd("sudo reboot", raise_stderr=False)
        time.sleep(10)
        self.check_connectable(self.reboot_timeout)


class FwupdUpdateState(Enum):
    FWUPD_UPDATE_STATE_UNKNOWN = 0
    FWUPD_UPDATE_STATE_PENDING = auto()
    FWUPD_UPDATE_STATE_SUCCESS = auto()
    FWUPD_UPDATE_STATE_FAILED = auto()
    FWUPD_UPDATE_STATE_NEEDS_REBOOT = auto()
    FWUPD_UPDATE_STATE_FAILED_TRANSIENT = auto()
    FWUPD_UPDATE_STATE_LAST = auto()
