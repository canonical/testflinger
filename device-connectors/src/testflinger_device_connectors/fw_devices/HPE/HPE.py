"""Device class for flashing firmware on HPE server machines"""

import subprocess
import json
import os
import logging
import time
import requests
import re
from testflinger_device_connectors import logmsg
from testflinger_device_connectors.fw_devices.base import (
    OEMDevice,
    SSH_OPTS,
)
from typing import Tuple

"""HPE firmware repository and index file"""
HPE_SDR = "https://downloads.linux.hpe.com/SDR"
HPE_SDR_REPO = f"{HPE_SDR}/repo"
FW_REPOS = {
    "rl": "rlcp",
    "gen10": "fwpp-gen10",
    "gen11": "fwpp-gen11",
}
INDEX_FILE = "fwrepo.json"


class HPEDevice(OEMDevice):
    """Device class for HPE server machines"""

    fw_update_type = "OEM-defined"
    vendor = ["HPE"]
    reboot_timeout = 1800

    def __init__(
        self,
        ipaddr: str,
        user: str,
        bmc_ip: str,
        bmc_user: str,
        bmc_password: str,
    ):
        super().__init__(ipaddr, user)
        self.bmc_ip = bmc_ip
        self.bmc_user = bmc_user
        self.bmc_password = bmc_password
        self.fwrepo_index = {}
        self._install_ilorest()
        self._login_ilo()

    def _install_ilorest(self):
        """Install stable/current ilorest deb from HPE SDR"""
        install_cmd = [
            f"curl -fsSL {HPE_SDR}/hpePublicKey2048_key1.pub"
            + " | sudo gpg --dearmor -o /etc/apt/trusted.gpg.d/hpe.gpg",
            f"echo '# HPE ilorest\ndeb {HPE_SDR_REPO}/ilorest stable/current"
            + " non-free' > /etc/apt/sources.list.d/ilorest.list",
            "apt update",
            "apt install -y ilorest",
        ]
        for cmd in install_cmd:
            r = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
            )
        rc, stdout, stderr = self.run_cmd("--version")
        logmsg(logging.INFO, f"successfully installed {stdout}")

    def run_cmd(
        self, cmds: str, raise_stderr: bool = True, timeout: int = 30
    ) -> Tuple[int, str, str]:
        """
        Execute ilorest command

        :param cmds:         ilorest commands
        :param raise_stderr: when set to `True`, raise RuntimeError if return
                             code != 0, otherwise ignore it
        :param timeout:      timeout for the command response
        :returns:            return code, stdout, stderr
        """
        ilorest_prefix = "ilorest --nologo "
        if isinstance(cmds, list):
            ilorest_cmd = ";".join([ilorest_prefix + cmd for cmd in cmds])
        else:
            ilorest_cmd = ilorest_prefix + cmds
        r = subprocess.run(
            ilorest_cmd, shell=True, capture_output=True, timeout=timeout
        )
        rc, stdout, stderr = (
            r.returncode,
            r.stdout.decode().strip(),
            r.stderr.decode().strip(),
        )

        if raise_stderr and rc != 0:
            err_msg = "Failed to execute %s:\n [%d] %s %s" % (
                ilorest_cmd,
                rc,
                stdout,
                stderr,
            )
            logmsg(logging.ERROR, err_msg)
            raise RuntimeError(err_msg)
        else:
            return rc, stdout, stderr

    def _login_ilo(self):
        """Log in HPE machine's iLO via ilorest command"""
        self.run_cmd(
            "login %s -u %s -p %s"
            % (self.bmc_ip, self.bmc_user, self.bmc_password)
        )

    def _login_out(self):
        """Log out HPE machine's iLO via ilorest command"""
        self.run_cmd("logout")

    def _repo_search(self, device_cls: str, targets: list) -> list:
        """
        Search FW file by filename, description, or target IDs

        :param device_cls: device class ID that allowed to be None
        :param targets:    a list of target ID associate to the FW
        :return:           a list of FW files with detailed information
        """
        fwpkg_data, temp_fw = {}, {}
        for spp, json_index in self.fwrepo_index.items():
            for fw_file in json_index:
                if any(
                    t in str(json_index[fw_file]["target"]) for t in targets
                ) and (
                    json_index[fw_file]["deviceclass"] == device_cls
                    or device_cls == None
                ):
                    if (
                        temp_fw == {}
                        or temp_fw["version"] < json_index[fw_file]["version"]
                    ):
                        temp_fw = {"file": fw_file, **json_index[fw_file]}
            if temp_fw:
                fwpkg_data[spp] = temp_fw
        return dict(sorted(fwpkg_data.items(), reverse=True))

    def get_fw_info(self):
        """
        Get current firmware version of all updatable devices on HPE machine,
        and print out devices with upgradable/downgradable versions
        """
        rc, stdout, stderr = self.run_cmd(
            "rawget /redfish/v1/UpdateService/FirmwareInventory/ --expand --silent"
        )
        fw_inventory = json.loads(stdout)["Members"]
        rc, stdout, stderr = self.run_cmd("systeminfo --system --json")
        dev_model = json.loads(stdout)["system"]["Model"]

        # load fw index meta file (fwrepo.json) according to HPE server model
        self.repo_name = [
            FW_REPOS[x]
            for x in list(FW_REPOS.keys())
            if x in dev_model.lower()
        ][0]
        logmsg(logging.INFO, f"HPE server model: {self.repo_name}")
        repo_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            self.repo_name,
        )
        logmsg(logging.INFO, repo_path)
        try:
            for spp in os.listdir(repo_path):
                with open(
                    os.path.join(repo_path, spp, INDEX_FILE),
                    "r",
                ) as json_index_file:
                    self.fwrepo_index[spp] = json.load(json_index_file)
        except:
            msg = f"Unable to open cached copy of index {spp}/{INDEX_FILE}"
            logmsg(logging.ERROR, msg)
            raise RuntimeError(msg)

        server_fw_info = []
        update_prio = [
            "system rom",
            "server platform services",
            "innovation engine",
            "ilo",
        ]
        for fw in fw_inventory:
            fwpkg_data = {}
            update_order = 5
            if fw["Updateable"]:
                update_order = 4
                if fw["Oem"]["Hpe"].get("Targets") != None:
                    fwpkg_data = self._repo_search2(
                        fw["Oem"]["Hpe"].get("DeviceClass"),
                        fw["Oem"]["Hpe"]["Targets"],
                    )
                for x in update_prio:
                    if x in fw["Name"].lower():
                        update_order = update_prio.index(x)
            server_fw_info.append(
                dict(
                    {
                        "Firmware Name": fw["Name"],
                        "Firmware Version": fw["Version"],
                        "Location": fw["Oem"]["Hpe"]["DeviceContext"],
                        "Fwpkg Available": fwpkg_data,
                        "Update Order": update_order,
                    }
                )
            )
        self.fw_info = sorted(server_fw_info, key=lambda x: x["Update Order"])
        logmsg(logging.INFO, f"firmware on HPE machine:\n{self.fw_info}")

    def _get_IML(self):
        """Fetch firmware flash log from iLO IML"""
        rc, stdout, stderr = self.run_cmd(
            "serverlogs --selectlog=IML --filter Oem/Hpe/Class=32 --json",
            raise_stderr=False,
        )
        if rc == 0:
            iml_fw_update = json.loads(stdout)
        elif rc == 6:  # rc 6: Filter returned no matches
            iml_fw_update = []
        return iml_fw_update

    def _flash_fwpkg(self, spp: str) -> bool:
        """
        Flash FW via ilorest and return `True` if a machine reboot is needed

        :param spp: HPE SPP released date = repo folder name
        :return:    `True` if reboot is needed, `False` otherwise
        """

        # TODO: 1. skip firmware update if current version match the version
        #          infwpkg (need to resolve version format mismatch issue)
        #       2. comparing "minimum_active_version" with "current version"

        def purify_ver(ver_string):
            ver_num = re.sub(
                "\.|\)|\(|\/|-|_",
                " ",
                ver_string,
            ).strip()
            return "".join(map(str, list(map(int, ver_num.split(" ")))))

        logmsg(
            logging.INFO,
            f"Start flashing all firmware with files in SPP {spp}",
        )
        reboot = False
        install_list = []

        for fw in self.fw_info:
            if fw.get("Fwpkg Available", {}).get(spp):
                current_ver = (
                    re.match(
                        r"([^a-zA-Z]*)", fw["Firmware Version"].split("v")[-1]
                    )
                    .group(1)
                    .replace(" ", "")
                )
                new_ver = fw["Fwpkg Available"][spp]["version"]
                min_req_ver = fw["Fwpkg Available"][spp][
                    "minimum_active_version"
                ]
                if purify_ver(current_ver) == purify_ver(new_ver):
                    logmsg(
                        logging.INFO,
                        f"[{fw['Firmware Name']}] no update is needed,"
                        + f"already {fw['Firmware Version']}",
                    )
                elif min_req_ver != "null" and purify_ver(
                    current_ver
                ) < purify_ver(min_req_ver):
                    logmsg(
                        logging.INFO,
                        f"[{fw['Firmware Name']}] current firmware "
                        + f"{fw['Firmware Version']} not meet minimum "
                        + f"active version {min_req_ver}",
                    )
                else:
                    install_list.append(
                        self._download_fwpkg(
                            spp, fw["Fwpkg Available"][spp]["file"]
                        )
                    )
                    fw["targetVersion"] = fw["Fwpkg Available"][spp]["version"]
        if install_list == []:
            return reboot

        # get the IML before firmware flash
        self.iml_pre_update = self._get_IML()

        # check and clear the task queue to prevent blocking firmware flash
        logmsg(logging.INFO, "check and clear iLO taskqueue")

        rc, stdout, stderr = self.run_cmd("taskqueue", raise_stderr=False)
        if "No tasks found" not in stdout:
            self.run_cmd("taskqueue -c")
            rc, stdout, stderr = self.run_cmd("taskqueue", raise_stderr=False)
            if "No tasks found" not in stdout:
                msg = (
                    "there's still incomplete task(s) in task queue, which"
                    + f" may impact firmware upgrade actions: {taskqueue}"
                )
                logmsg(logging.WARNING, msg)

        # start flashing firmware in the install list
        flash_result = dict()
        for file in install_list:
            self._login_ilo()
            file_name = file.split("/")[-1]
            logmsg(logging.INFO, f"start flashing {file_name}")
            rc, stdout, stderr = self.run_cmd(
                f"flashfwpkg --forceupload {file}", raise_stderr=False
            )

            result = re.sub(r"Updating: .\r", "", stdout)
            flash_result[file.split("/")[-1]] = result
            logmsg(logging.INFO, result)

            # wait for iLO to complete reboot before proceed to next operation
            if "ilo will reboot" in stdout.lower():
                logmsg(logging.INFO, "wait until iLO complete reboot")
                for retry in range(20):
                    time.sleep(10)
                    if (
                        subprocess.check_output(
                            f"ping {self.bmc_ip} -c 5 > /dev/null; echo $?",
                            stderr=subprocess.STDOUT,
                            shell=True,
                        )
                        .decode()
                        .strip()
                        == "0"
                    ):
                        break
                time.sleep(10)
        self._login_out()

        if any(
            reboot_str in str(flash_result.values()).lower()
            for reboot_str in ["flash on reboot", "a reboot is required"]
        ):
            reboot = True
        return reboot

    def _download_fwpkg(self, spp, fw_file):
        """
        Download fwpkg file from HPE repository to local dir /home/HPE_FW

        :param spp:     spp release date
        :param fw_file: fwpkg file name
        :return:        full path of downloaded fwpkg file
        """
        url = f"{HPE_SDR_REPO}/{self.repo_name}/{spp}/{fw_file}"
        FW_DIR = "/home/HPE_FW"
        fw_file_path = os.path.join(FW_DIR, fw_file)
        try:
            os.mkdir(FW_DIR)
        except OSError as error:
            pass
        if os.path.isfile(fw_file_path):
            return fw_file_path
        logmsg(logging.INFO, f"downloading {fw_file}")
        try:
            html_request = requests.get(url)
            if html_request.status_code != 200:
                raise Exception(html_request.status_code)
            else:
                with open(fw_file_path, "wb") as firmware_file:
                    firmware_file.write(html_request.content)
        except Exception as error:
            if str(error) == "404":
                raise RuntimeError(
                    "Unable to download firmware (404 not found): %s" % url
                )
            elif str(error) == "401":
                raise RuntimeError(
                    "Unable to download firmware (401 not authorized)"
                )
            else:
                raise RuntimeError("Unable to download. %s" % str(error))
        return fw_file_path

    def check_results(self) -> bool:
        """
        Check if all firmware flash results are listed in iLO IML

        :return:  `True` if all firmware flash results are listed, `False`
                  otherwise
        """
        update_result = True
        self._login_ilo()
        iml_post_update = self._get_IML()
        fw_iml = []
        for iml in iml_post_update:
            if not any(
                iml_pre["Oem"]["Hpe"]["EventNumber"]
                == iml["Oem"]["Hpe"]["EventNumber"]
                for iml_pre in self.iml_pre_update
            ):
                fw_iml.append(iml)

        for fw in self.fw_info:
            if "targetVersion" not in fw:
                continue
            if any(fw["targetVersion"] in iml["Message"] for iml in fw_iml):
                msg = (
                    f"[{fw['Firmware Name']}] firmware flashed "
                    + f"{fw['Firmware Version']} → {fw['targetVersion']}"
                )
                log_level = logging.INFO
            else:
                msg = (
                    f"[{fw['Firmware Name']}] firmware flashed "
                    + f"{fw['Firmware Version']} → {fw['targetVersion']}"
                )
                log_level = logging.ERROR
                update_result = False
            logmsg(log_level, msg)
        self._login_out()
        return update_result

    def upgrade(self):
        """Upgrade HPE machine firmware with the latest SPP"""
        target_spp = list(self.fwrepo_index.keys())[0]
        return self._flash_fwpkg(target_spp)

    def downgrade(self, target_spp):
        """Downgrade HPE machine firmware with the given (previous) SPP"""
        return self._flash_fwpkg(target_spp)

    def reboot(self):
        """Reboot HPE machine via iLO"""
        logmsg(logging.INFO, "reboot DUT")
        self._login_ilo()
        self.run_cmd("reboot")
        self._monitor_poststate("FinishedPost", self.reboot_timeout)
        self.check_connectable(self.reboot_timeout)

    def _monitor_poststate(self, state: str, timeout: int):
        """
        After HPE machine reboot, monitor the POST state to until the target
        state is reached.

        :param state:   target POST state
        :param timeout: wait time for regaining DUT access
        """
        cmd = [
            "select ComputerSystem --refresh",
            "get Oem/Hpe/PostState --json",
        ]
        timeout_start = time.time()
        while time.time() < timeout_start + timeout:
            rc, stdout, stderr = self.run_cmd(cmd)
            if state in stdout:
                delta = time.time() - timeout_start
                msg = f"HPE machine reaches {state} after {int(delta)}s"
                logmsg(logging.INFO, msg)
                return
            else:
                time.sleep(10)
        err_msg = f"HPE machine failed to reach {state} after {timeout}s"
        raise RuntimeError(err_msg)
