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
        # self.run_cmd("sudo apt update && sudo apt install fwupd")

    def run_cmd(self, cmd, raise_stderr=True, timeout=30):
        """
        Execute command on DUT via SSH

        :returns: return code, stdout, stderr
        :rtype: int, string, string
        """
        if self.password == "":
            ssh_cmd = 'ssh -t %s %s@%s "%s"' % (
                SSH_OPTS,
                self.user,
                self.ipaddr,
                cmd,
            )
        else:
            ssh_cmd = (
                'sshpass -p %s  ssh -t %s %s@%s "%s"'
                % (self.password, SSH_OPTS, self.user, self.ipaddr, cmd),
            )
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
        logger.debug("Run command: %s" % ssh_cmd)
        if raise_stderr and rc != 0:
            err_msg = "Failed to execute %s:\n [%d] %s %s" % (
                cmd,
                rc,
                stdout,
                stderr,
            )
            logger.debug(err_msg)
            raise RuntimeError(err_msg)
        else:
            return rc, stdout, stderr

    def get_fw_info(self):
        """
        Get current firmware version of all updatable devices on DUT
        And print out devices with upgradable/downgradable versions
        """
        logger.info("collect firmware info")
        self.run_cmd("sudo fwupdmgr refresh --force")
        rc, stdout, stderr = self.run_cmd("sudo fwupdmgr get-devices --json")
        logger.debug("$fwupdmgr get-devices = \n%s" % stdout)
        for dev in json.loads(stdout)["Devices"]:
            if "Flags" in dev:
                if "updatable" in dev["Flags"]:
                    self.fw_info.append(dev)

        for dev in self.fw_info:
            if "Version" in dev:
                dev_name = dev["Name"] if "Name" in dev else dev["DeviceId"]
                msg = "[%s] current version: %s" % (dev_name, dev["Version"])
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
                    vers = " - LVFS upgradable version(s): %s" % ", ".join(
                        higher_ver
                    )
                if lower_ver != []:
                    vers = (
                        vers
                        + " - LVFS downgradable version(s): %s"
                        % ", ".join(lower_ver)
                    )
                if vers:
                    msg = msg + vers
                    print(msg)
            else:
                msg = msg + " - no available firmware on LVFS"
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
                        "[%s] try upgrading to %s"
                        % (dev_name, latest_ver["Version"])
                    )
                    dev["targetVersion"] = latest_ver["Version"]
                    rc, stdout, stderr = self.run_cmd(
                        "sudo fwupdmgr upgrade %s -y --no-reboot-check"
                        % dev["DeviceId"],
                        raise_stderr=False,
                    )
                    if rc == 0:
                        logger.debug(stdout)
                        reboot = True
                    else:
                        logger.info(
                            "[%s] Failed to upgrade %s"
                            % (dev_name, latest_ver["Version"])
                        )
                        logger.debug(stdout)
                        logger.debug(stderr)
                else:
                    logger.info(
                        "[%s] unsupported Flags: %s"
                        % (dev_name, str(latest_ver["Flags"]))
                    )
            else:
                logger.info(
                    "[%s] already the latest available firmware version"
                    % dev_name
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
            except KeyError:
                continue
            except IndexError:
                continue
            if dev["Version"] != prev_ver["Version"]:
                if (
                    "is-downgrade"
                    in prev_ver["Flags"]
                    # and "blocked-version" not in prev_ver["Flags"]
                ):
                    dev["targetVersion"] = prev_ver["Version"]
                    logger.info(
                        "[%s] try downgrading to %s"
                        % (dev_name, prev_ver["Version"])
                    )
                    rc, stdout, stderr = self.run_cmd(
                        "sudo fwupdmgr download %s" % prev_ver["Uri"],
                        raise_stderr=False,
                    )
                    if rc == 0:
                        pass
                    elif rc == 1 and "already exists" in stderr:
                        pass
                    else:
                        raise RuntimeError(
                            "[%s] fail to download firmware file from LVFS\ntarget: %s\nerror: %s"
                            % (dev_name, prev_ver["Uri"], stdout)
                        )
                    rc, stdout, stderr = self.run_cmd(
                        "sudo fwupdmgr install %s -y --no-reboot-check --allow-older"
                        % prev_ver["Uri"].split("/")[-1],
                        raise_stderr=False,
                    )
                    if rc == 0:
                        logger.debug(stdout)
                        reboot = True
                    else:
                        logger.info(
                            "[%s] fail to force install (downgrade) firmware %s"
                            % (dev_name, prev_ver["Uri"].split("/")[-1])
                        )
                        logger.debug(stdout)
                        logger.debug(stderr)
                else:
                    logger.info(
                        "[%s] unsupported Flags: %s"
                        % (dev_name, str(prev_ver["Flags"]))
                    )
            else:
                logger.info(
                    "[%s] already the previous version of latest release"
                    % dev_name
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
                "sudo fwupdmgr get-results %s --json" % dev["DeviceId"]
            )
            get_results = json.loads(stdout)
            logger.debug("$fwupdmgr get-result = \n%s" % stdout)
            try:
                new_fw = get_results["Releases"][0]
                update_state = get_results["UpdateState"]
            except KeyError:
                msg = "[%s] unable to determine if new firmware is landed due to missing results"
                logger.info(msg)
                print(msg)
                fwupd_result = False
                continue

            if new_fw["Version"] == expected_ver and update_state == 2:
                msg = "[%s] firmware flashed %s → %s" % (
                    dev_name,
                    dev["Version"],
                    expected_ver,
                )
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
                msg = "[%s] firmware upgrade failed. %s" % (
                    dev_name,
                    FwupdUpdateState[update_state],
                )
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
        logger.info(
            "check and wait for %ss until SSH is connectable" % timeout
        )
        status = "1"
        timeout_start = time.time()

        while status != "0" and time.time() < timeout_start + timeout:
            status = subprocess.check_output(
                "timeout 10 ssh %s %s@%s /bin/true 2>/dev/null; echo $?"
                % (SSH_OPTS, self.user, self.ipaddr),
                shell=True,
                universal_newlines=True,
            ).strip()
        if status != "0":
            logger.error(f"Failed to SSH to {self.ipaddr} after {timeout}s")
            raise RuntimeError(
                f"Failed to SSH to {self.ipaddr} after {timeout}s"
            )
        else:
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
