"""Device class for flashing firmware on device supported by LVFS-fwupd"""


import subprocess
import json
import time
from devices.base import AbstractDevice, logger

SSH_OPTS = "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"


class LVFSDevice(AbstractDevice):
    """Device class for devices supported by LVFS-fwupd"""

    fw_update_type = "LVFS"
    vendor = ["HP", "Dell Inc.", "LENOVO"]
    reboot_timeout = 600

    def __init__(self, ipaddr: str, user: str, password: str):
        super().__init__(ipaddr, user, password)

    def run_cmd(
        self, cmd: str, raise_stderr: bool = True, timeout: int = 30
    ) -> tuple[int, str, str]:
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
            ssh_cmd = f'sshpass -p {self.password}  ssh -t {SSH_OPTS} {self.user}@{self.ipaddr} "{cmd}"'
        logger.debug("Run command: %s" % ssh_cmd)
        r = subprocess.run(
            ssh_cmd,
            shell=True,
            capture_output=True,
            timeout=timeout,
        )
        rc, stdout, stderr = (
            r.returncode,
            r.stdout.decode().strip(),
            r.stderr.decode().strip(),
        )
        if raise_stderr and rc != 0:
            err_msg = f"Failed to execute {cmd}:\n [{rc}] {stdout} {stderr}"
            logger.debug(err_msg)
            raise RuntimeError(err_msg)
        return rc, stdout, stderr

    def get_fw_info(self):
        """
        Get current firmware version of all updatable devices on DUT, and print
        out devices with upgradable/downgradable versions
        """
        self._install_fwupd()
        logger.info("collect firmware info")
        self.run_cmd("sudo fwupdmgr refresh --force")
        rc, stdout, stderr = self.run_cmd("sudo fwupdmgr get-devices --json")
        logger.debug("$fwupdmgr get-devices = \n%s" % stdout)
        self._parse_fwupd_raw(stdout)

    def _install_fwupd(self):
        self.run_cmd("sudo apt update", timeout=120)
        self.run_cmd("sudo apt install -y fwupd")
        rc, stdout, stderr = self.run_cmd("sudo fwupdmgr --version")
        logger.debug(stdout)

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
                    vers = f" - LVFS upgradable version(s): {', '.join(higher_ver)}"
                if lower_ver != []:
                    vers += f" - LVFS downgradable version(s): {', '.join(lower_ver)}"
                if vers:
                    msg += vers
                    print(msg)
            else:
                msg += " - no available firmware on LVFS"
            if msg:
                logger.info(msg)

    def upgrade(self) -> bool:
        """
        Upgrade all devices firmware to latest version if available on LVFS

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
                        "[%s] try upgrading to %s"
                        % (dev_name, latest_ver["Version"])
                    )
                    dev["targetVersion"] = latest_ver["Version"]
                    rc, stdout, stderr = self.run_cmd(
                        f"sudo fwupdmgr upgrade {dev['DeviceId']} -y --no-reboot-check",
                        raise_stderr=False,
                    )
                    if rc == 0:
                        logger.debug(stdout)
                        reboot = True
                    else:
                        logger.error(
                            "[%s] Failed to upgrade %s"
                            % (dev_name, latest_ver["Version"])
                        )
                        logger.debug(stdout)
                        logger.debug(stderr)
                else:
                    logger.debug(
                        "[%s] unsupported Flags: %s"
                        % (dev_name, str(latest_ver["Flags"]))
                    )
            else:
                logger.info(
                    "[%s] already the latest available firmware version"
                    % dev_name
                )
        return reboot

    def downgrade(self) -> bool:
        """
        Downgrade all devices firmware to 2nd new version if available on LVFS

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
            if dev["Version"] != prev_ver["Version"]:
                if "is-downgrade" in prev_ver["Flags"]:
                    dev["targetVersion"] = prev_ver["Version"]
                    fw_file = prev_ver["Uri"].split("/")[-1]
                    logger.info(
                        "[%s] try downgrading to {prev_ver['Version']}"
                        % dev_name
                    )
                    rc, stdout, stderr = self.run_cmd(
                        f"sudo fwupdmgr download {prev_ver['Uri']}",
                        raise_stderr=False,
                    )
                    if not (
                        rc == 0 or (rc == 1 and "already exists" in stderr)
                    ):
                        raise RuntimeError(
                            f"[{dev_name}] fail to download firmware file from LVFS\ntarget: {prev_ver['Uri']}\nerror: {stdout}"
                        )
                    rc, stdout, stderr = self.run_cmd(
                        f"sudo fwupdmgr install {fw_file} -y --no-reboot-check --allow-older",
                        raise_stderr=False,
                    )
                    if rc == 0:
                        logger.debug(stdout)
                        reboot = True
                    else:
                        logger.error(
                            "[%s] fail to force install (downgrade) firmware %s"
                            % (dev_name, fw_file)
                        )
                        logger.debug(stdout)
                        logger.debug(stderr)
                else:
                    logger.debug(
                        "[%s] unsupported Flags: %s"
                        % (dev_name, prev_ver["Flags"])
                    )
            else:
                logger.info(
                    "[%s] already the previous version of latest release"
                    % dev_name
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
            logger.debug("$fwupdmgr get-result = \n%s" % stdout)
            try:
                new_fw = get_results["Releases"][0]
                update_state = get_results["UpdateState"]
            except KeyError:
                msg = f"[{dev_name}] unable to determine if new firmware is landed due to missing results"
                logger.info(msg)
                print(msg)
                fwupd_result = False
                continue

            if new_fw["Version"] == expected_ver and update_state == 2:
                msg = f"[{dev_name}] firmware flashed {dev['Version']} → {expected_ver}"
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
                msg = f"[{dev_name}] firmware upgrade failed. {FwupdUpdateState[update_state]}"
                fwupd_result = False
            print(msg)
            logger.info(msg)

        return fwupd_result

    def check_connectable(self, timeout: int):
        """
        After DUT reboot, check if SSH to DUT works within a given timeout period

        :param timeout: wait time for regaining DUT access
        """
        logger.info(
            "check and wait for %ss until SSH is connectable" % timeout
        )
        status = "1"
        timeout_start = time.time()

        while status != "0" and time.time() < timeout_start + timeout:
            status = subprocess.check_output(
                f"timeout 10 ssh {SSH_OPTS} {self.user}@{self.ipaddr} /bin/true 2>/dev/null; echo $?",
                shell=True,
                universal_newlines=True,
            ).strip()
        if status != "0":
            err_msg = f"Failed to SSH to {self.ipaddr} after {timeout}s"
            logger.error(err_msg)
            raise RuntimeError(err_msg)
        delta = time.time() - timeout_start
        logger.info("%s is SSHable after %ss" % (self.ipaddr, int(delta)))

    def reboot(self):
        """Reboot the DUT from OS"""

        logger.info("reboot DUT")
        self.run_cmd("sudo reboot", raise_stderr=False)
        time.sleep(10)
        self.check_connectable(self.reboot_timeout)


class LenovoNB(LVFSDevice):
    """
    Place-holder for device class for Lenovo Notebook devices which requires
    battery attached for flashing firmware
    """

    fw_update_type = "LVFS-ext"
    vendor = "LENOVO"
