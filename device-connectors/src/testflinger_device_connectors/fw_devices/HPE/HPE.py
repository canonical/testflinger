"""Device class for flashing firmware on HPE server machines"""

import subprocess
import json
import os
import logging
import time
import requests
import re
from testflinger_device_connectors.fw_devices.base import OEMDevice
from typing import Tuple

logger = logging.getLogger()


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
            " | sudo gpg --dearmor | sudo tee"
            " /etc/apt/trusted.gpg.d/hpe.gpg > /dev/null",
            f"echo '# HPE ilorest\n"
            f"deb {HPE_SDR_REPO}/ilorest stable/current non-free'"
            " > /etc/apt/sources.list.d/ilorest.list",
            "apt update",
            "apt install -y ilorest",
        ]
        for cmd in install_cmd:
            subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
            )
        rc, stdout, stderr = self.run_cmd("--version")
        if rc == 0:
            logger.info("successfully installed %s" % stdout)
        else:
            raise RuntimeError("failed to install ilorest")

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
            err_msg = (
                f"failed to execute {ilorest_cmd}:\n[{rc}] {stdout} {stderr}"
            )
            raise RuntimeError(err_msg)
        else:
            return rc, stdout, stderr

    def _login_ilo(self):
        """Log in HPE machine's iLO"""
        self.run_cmd(
            f"login {self.bmc_ip} -u {self.bmc_user} -p {self.bmc_password}"
        )

    def _logout_ilo(self):
        """Log out HPE machine's iLO"""
        self.run_cmd("logout")

    def _repo_search(self, device_cls: str, targets: list) -> list:
        """
        Search FW file by filename, description, or target IDs

        :param device_cls: device class ID that allowed to be None
        :param targets:    a list of target ID associate to the FW
        :return:           a list of FW files with detailed information
        """
        fwpkg_data = {}
        for spp, json_index in self.fwrepo_index.items():
            temp_fw = {}
            for fw_file in json_index:
                if any(
                    t in str(json_index[fw_file]["target"]) for t in targets
                ) and (
                    json_index[fw_file]["deviceclass"] == device_cls
                    or device_cls is None
                ):
                    if (
                        temp_fw == {}
                        or temp_fw["version"] < json_index[fw_file]["version"]
                    ):
                        temp_fw = {"file": fw_file, **json_index[fw_file]}
            if temp_fw:
                fwpkg_data[spp] = temp_fw
        return dict(sorted(fwpkg_data.items(), reverse=True))

    def _rawget_firmware_inventory(self):
        """Get iLO firmware inventory raw data"""
        rc, stdout, stderr = self.run_cmd(
            "rawget /redfish/v1/UpdateService/FirmwareInventory/"
            " --expand --silent"
        )
        return json.loads(stdout)["Members"]

    def _get_hpe_fw_repo(self):
        """
        Get firmware index file (fwrepo.json) according to server model
        """
        rc, stdout, stderr = self.run_cmd("systeminfo --system --json")
        dev_model = json.loads(stdout)["system"]["Model"]
        self.repo_name = [
            FW_REPOS[x]
            for x in list(FW_REPOS.keys())
            if x in dev_model.lower()
        ][0]
        logger.info("HPE server model: %s" % self.repo_name)
        # TODO: instead of using local files, downloading the index files from
        #       HPE SDR once HPE updates them with multiple target IDs
        repo_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "fwrepo",
            self.repo_name,
        )
        json_index = {}
        try:
            for spp in os.listdir(repo_path):
                with open(
                    os.path.join(repo_path, spp, INDEX_FILE),
                    "r",
                ) as json_index_file:
                    json_index[spp] = json.load(json_index_file)
        except IOError:
            msg = f"Unable to open cached copy of index {spp}/{INDEX_FILE}"
            raise RuntimeError(msg)
        self.fwrepo_index = dict(sorted(json_index.items(), reverse=True))

    def get_fw_info(self):
        """
        Get current firmware version of all updatable devices on HPE machine,
        and print out devices with upgradable/downgradable versions
        """
        fw_inventory = self._rawget_firmware_inventory()
        self._get_hpe_fw_repo()
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
                if fw["Oem"]["Hpe"].get("Targets") is not None:
                    fwpkg_data = self._repo_search(
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
        logger.info("firmware on HPE machine:\n%s" % self.fw_info)

    def _purify_ver(self, ver_string: str) -> str:
        """
        Extract pure version number and unify the format

        :param ver_string: version from iLO or fwrepo.json
        :return:           purified numeric version
        """
        ver_num = re.sub(
            r"\.|\)|\(|\/|-|_",
            " ",
            re.match(r"([^a-zA-Z]*)", ver_string.split("v")[-1])
            .group(1)
            .replace(" ", ""),
        ).strip()
        return ".".join(map(str, list(map(int, ver_num.split(" ")))))

    def _flash_fwpkg(self, spp: str) -> bool:
        """
        Flash FW via ilorest and return `True` if a machine reboot is needed

        :param spp: HPE SPP released date = repo folder name
        :return:    `True` if reboot is needed, `False` otherwise
        """
        if spp not in str(self.fw_info):
            raise RuntimeError(
                f"SPP {spp} is not available in HPE FW repository."
                " Please check if it's a valid SPP."
            )
        logger.info("start flashing all firmware with files in SPP %s" % spp)
        install_list = []
        for fw in self.fw_info:
            if fw.get("Fwpkg Available", {}).get(spp):
                current_ver = fw["Firmware Version"]
                new_ver = fw["Fwpkg Available"][spp]["version"]
                min_req_ver = fw["Fwpkg Available"][spp][
                    "minimum_active_version"
                ]
                if self._purify_ver(current_ver) == self._purify_ver(new_ver):
                    logger.info(
                        "[%s] no update is needed, already %s"
                        % (fw["Firmware Name"], fw["Firmware Version"])
                    )
                elif min_req_ver != "null" and self._purify_ver(
                    current_ver
                ) < self._purify_ver(min_req_ver):
                    logger.error(
                        "[%s] current firmware %s doesn't meet "
                        "minimum active version %s"
                        % (
                            fw["Firmware Name"],
                            fw["Firmware Version"],
                            min_req_ver,
                        )
                    )
                else:
                    logger.info(
                        "[%s] update current firmware %s to %s"
                        % (
                            fw["Firmware Name"],
                            fw["Firmware Version"],
                            fw["Fwpkg Available"][spp]["version"],
                        )
                    )
                    install_list.append(
                        self._download_fwpkg(
                            spp, fw["Fwpkg Available"][spp]["file"]
                        )
                    )
                    fw["targetVersion"] = fw["Fwpkg Available"][spp]["version"]
        if install_list == []:
            return False

        # check and clear the task queue to prevent blocking firmware flash
        logger.info("check and clear iLO taskqueue")
        rc, stdout, stderr = self.run_cmd("taskqueue", raise_stderr=False)
        if "No tasks found" not in stdout:
            self.run_cmd("taskqueue -c")
            rc, stdout, stderr = self.run_cmd("taskqueue", raise_stderr=False)
            if "No tasks found" not in stdout:
                msg = (
                    "there's still incomplete task(s) in task queue, "
                    f"which may impact firmware upgrade actions: {stdout}"
                )
                logger.warning(msg)

        # start flashing firmware files in the install list
        flash_result = dict()
        for file in install_list:
            self._login_ilo()
            file_name = file.split("/")[-1]
            logger.info("start flashing %s" % file_name)
            rc, stdout, stderr = self.run_cmd(
                f"flashfwpkg --forceupload {file}",
                raise_stderr=False,
                timeout=1200,
            )
            result = re.sub(r"Updating: .\r", "", stdout)
            flash_result[file_name] = result
            logger.info(result)

            # wait for iLO to complete reboot before proceed to next firmware
            if "ilo will reboot" in stdout.lower():
                logger.info("wait until iLO complete reboot")
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
        return True

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
        if not os.path.isdir(FW_DIR):
            os.mkdir(FW_DIR)
        if os.path.isfile(fw_file_path):
            logger.info("%s is already downloaded" % fw_file)
            return fw_file_path
        logger.info("downloading %s" % fw_file)
        try:
            html_request = requests.get(url)
            if html_request.status_code != 200:
                raise Exception(html_request.status_code)
            else:
                with open(fw_file_path, "wb") as firmware_file:
                    firmware_file.write(html_request.content)
        except Exception as error:
            raise RuntimeError(f"unable to download {str(error)}")
        return fw_file_path

    def check_results(self) -> bool:
        """
        Check if all firmware flash results are listed in iLO IML

        :return:  `True` if all firmware flash results are listed, `False`
                  otherwise
        """
        update_result = True
        self._login_ilo()
        fw_inventory = self._rawget_firmware_inventory()
        for fw in self.fw_info:
            if "targetVersion" not in fw:
                continue
            new_fw = next(
                (
                    new_fw
                    for new_fw in fw_inventory
                    if new_fw["Name"] == fw["Firmware Name"]
                ),
                None,
            )
            if new_fw and self._purify_ver(
                new_fw["Version"]
            ) == self._purify_ver(fw["targetVersion"]):
                logger.info(
                    "[%s] firmware flashed %s → %s"
                    % (
                        fw["Firmware Name"],
                        fw["Firmware Version"],
                        new_fw["Version"],
                    )
                )
            else:
                logger.error(
                    "[%s] firmware update failed" % fw["Firmware Name"]
                )
                update_result = False
        self._logout_ilo()
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
        logger.info("reboot DUT")
        timeout_start = time.time()
        # checking if Redfish resource is available after ilo reboot
        while time.time() < timeout_start + 60:
            self._login_ilo()
            rc, stdout, stderr = self.run_cmd("types")
            if "ComputerSystem" in stdout:
                break
            else:
                self._logout_ilo()
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
            rc, stdout, stderr = self.run_cmd(cmd, raise_stderr=False)
            if rc == 0 and state in stdout:
                delta = time.time() - timeout_start
                msg = f"HPE machine reaches {state} after {int(delta)}s"
                logger.info(msg)
                return
            else:
                time.sleep(10)
        err_msg = f"HPE machine failed to reach {state} after {timeout}s"
        raise RuntimeError(err_msg)
