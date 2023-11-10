"""Device class for flashing firmware on device supported by LVFS-fwupd"""


import subprocess
import json
import time
import logging
from typing import Tuple
from testflinger_device_connectors.fw_devices.base import AbstractDevice
from testflinger_device_connectors import logmsg


SSH_OPTS = "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"


class LVFSDevice(AbstractDevice):
    """Device class for devices supported by LVFS-fwupd"""

    fw_update_type = "LVFS"
    vendor = ["HP", "Dell Inc.", "LENOVO"]
    reboot_timeout = 900

    def run_cmd(
        self, cmd: str, raise_stderr: bool = True, timeout: int = 30
    ) -> Tuple[int, str, str]:
        """
        Execute command on the DUT via SSH

        :param cmd:          command to run on the DUT
        :param raise_stderr: when set to `True`, raise RuntimeError if return
                             code != 0, otherwise ignore it
        :param timeout:      timeout for the command response
        :returns:            return code, stdout, stderr
        """
        if self.password == "":
            ssh_cmd = f'ssh -t {SSH_OPTS} {self.user}@{self.ipaddr} "{cmd}"'
        else:
            ssh_cmd = (
                f"sshpass -p {self.password}  ssh -t {SSH_OPTS} "
                + f' {self.user}@{self.ipaddr} "{cmd}"'
            )
        try:
            r = subprocess.run(
                ssh_cmd,
                shell=True,
                capture_output=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as e:
            if raise_stderr:
                raise e
            else:
                return 124, f"command timeout after {timeout}s", ""
        rc, stdout, stderr = (
            r.returncode,
            r.stdout.decode().strip(),
            r.stderr.decode().strip(),
        )
        if raise_stderr and rc != 0:
            err_msg = f"Failed to execute {cmd}:\n [{rc}] {stdout} {stderr}"
            raise RuntimeError(err_msg)
        return rc, stdout, stderr

    def get_fw_info(self):
        """
        Get current firmware version of all updatable devices on DUT, and
        print out devices with upgradable/downgradable versions
        """
        self._install_fwupd()
        logmsg(logging.INFO, "collect firmware info")
        self.run_cmd("sudo fwupdmgr refresh --force")
        rc, stdout, stderr = self.run_cmd("sudo fwupdmgr get-devices --json")
        logmsg(logging.INFO, f"output of '$fwupdmgr get-devices'\n{stdout}")
        self._parse_fwupd_raw(stdout)

    def _install_fwupd(self):
        self.run_cmd("sudo apt update", raise_stderr=False, timeout=120)
        self.run_cmd("sudo apt install -y fwupd")
        rc, stdout, stderr = self.run_cmd("sudo fwupdmgr --version")
        logmsg(logging.INFO, f"fwupd version\n{stdout}")

    def _parse_fwupd_raw(self, fwupd_raw: str) -> bool:
        """
        Parse the output of ```$ fwupdmgr get-devices```

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
                logmsg(logging.INFO, msg)

    def upgrade(self) -> bool:
        """
        Upgrade all devices firmware to latest version if available on LVFS

        :return: `True` if upgrading is done and reboot is required, `False`
                 otherwise
        """
        logmsg(logging.INFO, "start upgrading")
        reboot = False
        for dev in self.fw_info:
            dev_name = dev["Name"] if "Name" in dev else dev["DeviceId"]
            try:
                latest_ver = dev["Releases"][0]
            except KeyError:
                continue
            if dev["Version"] != latest_ver["Version"]:
                if "is-upgrade" in latest_ver["Flags"]:
                    logmsg(
                        logging.INFO,
                        f"[{dev_name}] try upgrading to "
                        + f"{latest_ver['Version']}",
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
                        logmsg(
                            logging.ERROR,
                            f"[{dev_name}] Failed to upgrade to "
                            + f"{latest_ver['Version']}\n"
                            + f"error: {stdout}",
                        )
                else:
                    logmsg(
                        logging.INFO,
                        f"[{dev_name}] not an upgradable component",
                    )
            else:
                logmsg(
                    logging.INFO,
                    f"[{dev_name}] already the latest available firmware"
                    + "version",
                )
        return reboot

    def downgrade(self) -> bool:
        """
        Downgrade all devices firmware to 2nd new version if available on LVFS

        :return: `True` if downgrading is done and reboot is required, `False`
                 otherwise
        """
        logmsg(logging.INFO, "start downgrading")
        reboot = False
        for dev in self.fw_info:
            dev_name = dev["Name"] if "Name" in dev else dev["DeviceId"]
            try:
                prev_ver = dev["Releases"][1]
            except (KeyError, IndexError):
                continue
            if dev["Version"] == prev_ver["Version"]:
                logmsg(
                    logging.INFO,
                    f"[{dev_name}] already the previous version",
                )
                continue
            if "is-downgrade" in prev_ver["Flags"]:
                dev["targetVersion"] = prev_ver["Version"]
                fw_file = prev_ver["Uri"].split("/")[-1]
                logmsg(
                    logging.INFO,
                    f"[{dev_name}] try downgrading to {prev_ver['Version']}",
                )
                rc, stdout, stderr = self.run_cmd(
                    f"sudo fwupdmgr download {prev_ver['Uri']}",
                    raise_stderr=False,
                )
                if not (rc == 0 or (rc == 1 and "already exists" in stderr)):
                    raise RuntimeError(
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
                    logmsg(
                        logging.ERROR,
                        f"[{dev_name}] fail to force install (downgrade) "
                        + f"firmware {fw_file}\n"
                        + f"error: {stdout}",
                    )
            else:
                logmsg(
                    logging.INFO,
                    f"[{dev_name}] not a downgradable component",
                )
        return reboot

    def check_results(self) -> bool:
        """
        Get upgrade/downgrade result and validate if it succeeds

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
                msg = (
                    f"[{dev_name}] unable to determine if new firmware "
                    + "is landed due to missing results"
                )
                logmsg(logging.ERROR, msg)
                fwupd_result = False
                continue

            if new_fw["Version"] == expected_ver and update_state == 2:
                msg = (
                    f"[{dev_name}] firmware flashed {dev['Version']}"
                    + f" → {expected_ver}"
                )
                log_level = logging.INFO
            else:
                FwupdUpdateState = [
                    "FWUPD_UPDATE_STATE_UNKNOWN",
                    "FWUPD_UPDATE_STATE_PENDING",
                    "FWUPD_UPDATE_STATE_SUCCESS",
                    "FWUPD_UPDATE_STATE_FAILED",
                    "FWUPD_UPDATE_STATE_NEEDS_REBOOT",
                    "FWUPD_UPDATE_STATE_FAILED_TRANSIENT",
                    "FWUPD_UPDATE_STATE_LAST",
                ]
                update_err = get_results.get("UpdateError", "")
                msg = (
                    f"[{dev_name}] {FwupdUpdateState[update_state]}:"
                    + f" {update_err}"
                )
                log_level = logging.ERROR
                fwupd_result = False
            logmsg(log_level, msg)

        return fwupd_result

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
            status = subprocess.check_output(
                f"timeout 10 ssh {SSH_OPTS} {self.user}@{self.ipaddr} "
                + "/bin/true 2>/dev/null; echo $?",
                shell=True,
                universal_newlines=True,
            ).strip()
        if status != "0" and status != "124":
            err_msg = f"Failed to SSH to {self.ipaddr} after {timeout}s"
            logmsg(logging.ERROR, err_msg)
            raise RuntimeError(err_msg)
        delta = time.time() - timeout_start
        logmsg(logging.INFO, f"{self.ipaddr} is SSHable after {int(delta)}s")

    def reboot(self):
        """Reboot the DUT from OS"""
        logmsg(logging.INFO, "reboot DUT")
        self.run_cmd("sudo reboot", raise_stderr=False)
        time.sleep(10)
        self.check_connectable(self.reboot_timeout)
