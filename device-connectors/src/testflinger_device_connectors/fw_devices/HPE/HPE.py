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
from HPE_constants import *
from typing import Tuple


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
            f"curl {HPE_SDR}/hpePublicKey2048_key1.pub | sudo apt-key add -",
            f"echo '# HPE ilorest\ndeb {HPE_SDR}/repo/ilorest stable/current"
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

    def _repo_search(self, searchstring: str) -> list:
        """
        Search FW file by filename, description, or target IDs

        :param searchstring: support searching with mulitple keywords,
                             seperated by comma
        :return:             a list of FW files with detailed information
        """

        keywords = searchstring.split(",")
        fwpkg_data = {}

        for spp, json_index in self.fwrepo_index.items():
            for fw_file in json_index:
                if (
                    all(key.lower() in fw_file.lower() for key in keywords)
                    or all(
                        key.lower()
                        in json_index[fw_file]["description"].lower()
                        for key in keywords
                    )
                    or any(
                        searchstring.lower() in target.lower()
                        for target in json_index[fw_file]["target"]
                    )
                    and "Bmc" in str(json_index[fw_file]["updatableBy"])
                ):
                    fw_detail = {"file": fw_file, **json_index[fw_file]}
                    fwpkg_data[spp] = fw_detail
                    break

        return dict(sorted(fwpkg_data.items(), reverse=True))

    def get_fw_info(self):
        """
        Get current firmware version of all updatable devices on HPE machine,
        and print out devices with upgradable/downgradable versions
        """
        # collect firmware info via iLO
        rc, stdout, stderr = self.run_cmd(
            "systeminfo --firmware --system --json"
        )
        sysinfo = json.loads(stdout)
        fw_data, sys_data = sysinfo["firmware"], sysinfo["system"]
        current_fw = {k: v for k, v in fw_data.items() if v}

        rc, stdout, stderr = self.run_cmd(
            ["select HpeServerPciDevice", "list --json"]
        )
        pci_data = json.loads(stdout)
        dev_model = sys_data["Model"]

        # load fw index meta file (fwrepo.json) according to HPE server model
        self.repo_name = [
            FW_REPOS[x]
            for x in list(FW_REPOS.keys())
            if x in dev_model.lower()
        ][0]
        model_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            self.repo_name,
        )
        try:
            for item in os.listdir(model_path):
                fwrepo_path = os.path.join(model_path, item, INDEX_FILE)
                with open(
                    fwrepo_path,
                    "r",
                ) as json_index_file:
                    self.fwrepo_index[item] = json.load(json_index_file)
        except:
            msg = f"Unable to open cached copy of index {fwrepo_path}"
            logmsg(logging.ERROR, msg)
            raise RuntimeError(msg)

        # search and list available release for each firmware component
        server_fw_info = []
        for fw in current_fw:
            location = "N/A"
            update_order = 4
            fw_key = ""

            # skip checking as this FW is not provided in the repository
            if any(s.lower() in fw.lower() for s in IGNORE_LIST):
                location = (
                    "Bay 1/2"
                    if "power supply" in fw.lower()
                    else "System Board"
                )

            # UBM Backplane PIC PLDM Firmware
            elif "ubm" in fw.lower():
                location = "Embedded"
                fw_key = [x for x in fw.split() if "ubm" in x.lower()][0]

            # System Board Firmware
            elif any(s.lower() in fw.lower() for s in SYSTEM_BOARD_FW):
                location = "System Board"
                if "system rom" in fw.lower():
                    update_order = 0
                    fw_key = f"({fw_data[fw].split()[0]})"
                elif "server platform services" in fw.lower():
                    update_order = 2
                    if "gen11" in dev_model.lower():
                        fw_key = f"SC_{fw_data['System ROM'].split()[0]}"
                    else:
                        fw_key = [
                            GEN10_SPS_TYPES[x]
                            for x in GEN10_SPS_TYPES
                            if x.lower() in dev_model.lower()
                        ][0] + "_"
                elif "innovation engine" in fw.lower():
                    update_order = 1
                    fw_key = [
                        IE_TYPES[x]
                        for x in IE_TYPES
                        if x.lower() in dev_model.lower()
                    ][0] + "_"
                else:
                    if "ilo" in fw.lower():
                        update_order = 3
                    fw_key = [
                        x for x in SYSTEM_BOARD_FW if x.lower() in fw.lower()
                    ][0]

            # Embedde/PCIe Device
            else:
                for pci in pci_data:
                    if "Name" not in pci:
                        continue
                    if fw in pci["Name"]:
                        vid = format(int(pci["VendorID"]), "04X").lower()
                        did = format(int(pci["DeviceID"]), "04X").lower()
                        svid = format(
                            int(pci["SubsystemVendorID"]), "04X"
                        ).lower()
                        sdid = format(
                            int(pci["SubsystemDeviceID"]), "04X"
                        ).lower()
                        fw_key = "%s%s-%s%s%s" % (
                            TARGET_PREFIX,
                            vid,
                            did,
                            svid,
                            sdid,
                        )
                        location = pci["DeviceLocation"]
                        break

            fwpkg_data = self._repo_search(fw_key) if fw_key != "" else {}
            server_fw_info.append(
                dict(
                    {
                        "Firmware Name": fw,
                        "Firmware Version": fw_data[fw],
                        "Location": location,
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

        logmsg(
            logging.INFO,
            f"Start flashing all firmware with files in SPP {spp}",
        )
        reboot = False
        install_list = []
        for fw in self.fw_info:
            if fw.get("Fwpkg Available").get(spp) != None:
                install_list.append(
                    self._download_fwpkg(
                        spp, fw["Fwpkg Available"][spp]["file"]
                    )
                )
                fw["targetVersion"] = fw["Fwpkg Available"][spp]["version"]
        self.iml_pre_update = self._get_IML()

        # check and clear the task queue to prevent blocking the fw flashing
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
        url = f"{HPE_SDR}/{self.repo_name}/{spp}/{fw_file}"
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
