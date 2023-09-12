import subprocess
import json
import time
from devices.base import AbstractDevice, logger

SSH_OPTS = "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"


class LVFSDevice(AbstractDevice):
    fw_update_type = "LVFS"
    vendor = ["HP", "Dell Inc.", "LENOVO"]
    reboot_timeout = 600

    def __init__(self, ipaddr, user, password):
        super().__init__(ipaddr, user, password)

    def run_cmd(self, cmd, raise_stderr=True, timeout=30):
        """
        Execute command on DUT via SSH

        :returns: return code, stdout, stderr
        :rtype: int, string, string
        """
        if self.password == "":
            ssh_cmd = f'ssh -t {SSH_OPTS} {self.user}@{self.ipaddr} "{cmd}"'
        else:
            ssh_cmd = f'sshpass -p {self.password}  ssh -t {SSH_OPTS} {self.user}@{self.ipaddr} "{cmd}"'
        logger.debug(f"Run command: {ssh_cmd}")
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
        logger.debug(f"$fwupdmgr get-devices = \n{stdout}")
        self._parse_fwupd_raw(stdout)

    def _install_fwupd(self):
        self.run_cmd("sudo apt update", timeout=120)
        self.run_cmd("sudo apt install -y fwupd")
        rc, stdout, stderr = self.run_cmd("sudo fwupdmgr --version")
        logger.debug(stdout)

    def _parse_fwupd_raw(self, fwupd_raw: str):
        """
        Parse the output of $fwupdmgr get-devices

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
                    elif (
                        "is-downgrade"
                        in rel["Flags"]
                        # and "blocked-version" not in rel["Flags"]
                    ):
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
                msg = f"{msg} - no available firmware on LVFS"
            if msg:
                logger.info(msg)

    def upgrade(self):
        """
        Upgrade all devices firmware to latest version if available on LVFS

        :returns: if reboot is required
        :rtype: boolean
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
                        f"[{dev_name}] try upgrading to {latest_ver['Version']}"
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
                        logger.info(
                            f"[{dev_name}] Failed to upgrade {latest_ver['Version']}"
                        )
                        logger.debug(stdout)
                        logger.debug(stderr)
                else:
                    logger.info(
                        f"[{dev_name}] unsupported Flags: {str(latest_ver['Flags'])}"
                    )
            else:
                logger.info(
                    f"[{dev_name}] already the latest available firmware version"
                )
        return reboot

    def downgrade(self):
        """
        Downgrade all devices firmware to 2nd new version if available on LVFS

        :returns: if reboot is required
        :rtype: boolean
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
                if (
                    "is-downgrade"
                    in prev_ver["Flags"]
                    # and "blocked-version" not in prev_ver["Flags"]
                ):
                    dev["targetVersion"] = prev_ver["Version"]
                    fw_file = prev_ver["Uri"].split("/")[-1]
                    logger.info(
                        f"[{dev_name}] try downgrading to {prev_ver['Version']}"
                    )
                    rc, stdout, stderr = self.run_cmd(
                        f"sudo fwupdmgr download {prev_ver['Uri']}",
                        raise_stderr=False,
                    )
                    if rc == 0:
                        pass
                    elif rc == 1 and "already exists" in stderr:
                        pass
                    else:
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
                        logger.info(
                            f"[{dev_name}] fail to force install (downgrade) firmware {fw_file}"
                        )
                        logger.debug(stdout)
                        logger.debug(stderr)
                else:
                    logger.info(
                        f"[{dev_name}] unsupported Flags: {prev_ver['Flags']}"
                    )
            else:
                logger.info(
                    f"[{dev_name}] already the previous version of latest release"
                )
        return reboot

    def check_results(self):
        """
        Get upgrade/downgrade result and validate if it succeeds

        :returns: overall upgrade status
        :rtype: boolean
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
            logger.debug(f"$fwupdmgr get-result = \n{stdout}")
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

    def check_connectable(self, timeout):
        """
        After DUT reboot, check if SSH to DUT works within a given timeout period

        :param timeout: wait time for regaining DUT access
        :type timeout: int
        """
        logger.info(f"check and wait for {timeout}s until SSH is connectable")
        status = "1"
        timeout_start = time.time()

        while status != "0" and time.time() < timeout_start + timeout:
            status = subprocess.check_output(
                f"timeout 10 ssh {SSH_OPTS} {self.user}@{self.ipaddr} /bin/true 2>/dev/null; echo $?",
                shell=True,
                universal_newlines=True,
            ).strip()
        if status != "0":
            logger.error(f"Failed to SSH to {self.ipaddr} after {timeout}s")
            raise RuntimeError(
                f"Failed to SSH to {self.ipaddr} after {timeout}s"
            )
        delta = time.time() - timeout_start
        logger.info(f"{self.ipaddr} is SSHable after {int(delta)}s")

    def reboot(self):
        logger.info("reboot DUT")
        self.run_cmd("sudo reboot", raise_stderr=False)
        time.sleep(10)
        self.check_connectable(self.reboot_timeout)


class LenovoNB(LVFSDevice):
    fw_update_type = "LVFS-ext"
    vendor = "LENOVO"


# class HPNB(LVFSDevice):
# class DellNB(LVFSDevice)
