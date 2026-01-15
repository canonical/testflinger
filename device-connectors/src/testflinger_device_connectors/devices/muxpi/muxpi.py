# Copyright (C) 2017-2023 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Ubuntu Raspberry PI muxpi support code."""

import contextlib
import json
import logging
import shlex
import subprocess
import tempfile
import time
import urllib
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Union

import requests
import yaml

from testflinger_device_connectors.devices import (
    DefaultDevice,
    ProvisioningError,
    RecoveryError,
)

logger = logging.getLogger(__name__)


# should mirror `testflinger_agent.config.ATTACHMENTS_DIR`
# [TODO] Merge both constants into testflinger.common
ATTACHMENTS_DIR = "attachments"


class MuxPi:
    """Device Connector for MuxPi."""

    IMAGE_PATH_IDS = {
        "writable/usr/bin/firefox": "pi-desktop",
        "writable/etc": "ubuntu",
        "writable/system-data": "core",
        "ubuntu-seed/snaps": "core20",
        "cloudimg-rootfs/etc/cloud/cloud.cfg": "ubuntu-cpc",
    }

    def __init__(self, config=None, job_data=None):
        if config and job_data:
            with open(config) as configfile:
                self.config = yaml.safe_load(configfile)
            with open(job_data) as j:
                self.job_data = json.load(j)
        else:
            # For testing
            self.config = {"agent_name": "test"}
            self.job_data = {}
        self.agent_name = self.config.get("agent_name")
        self.mount_point = Path("/mnt") / self.agent_name

    def get_ssh_options(self):
        return (
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
        )

    def get_credentials(self):
        return (
            self.config.get("control_user", "ubuntu"),
            self.config.get("control_host"),
        )

    def _run_control(self, cmd, timeout=60):
        """Run a command on the control host over ssh.

        :param cmd:
            Command to run
        :param timeout:
            Timeout (default 60)
        :returns:
            Return output from the command, if any
        """
        control_user, control_host = self.get_credentials()
        ssh_cmd = [
            "ssh",
            *self.get_ssh_options(),
            f"{control_user}@{control_host}",
            cmd,
        ]
        try:
            output = subprocess.check_output(
                ssh_cmd, stderr=subprocess.STDOUT, timeout=timeout
            )
        except subprocess.SubprocessError as e:
            raise ProvisioningError(e.output) from e
        return output

    def _copy_to_control(self, local_file, remote_file):
        """Copy a file to the control host over ssh.

        :param local_file:
            Local filename
        :param remote_file:
            Remote filename
        """
        control_user, control_host = self.get_credentials()
        ssh_cmd = [
            "scp",
            *self.get_ssh_options(),
            local_file,
            f"{control_user}@{control_host}:{remote_file}",
        ]
        try:
            output = subprocess.check_output(ssh_cmd, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            raise ProvisioningError(e.output) from e
        return output

    def reboot_sdwire(self):
        """Reboot both control host and DUT to ensure SDwire be in a good state
        before provisioning.
        """
        if not self.config.get("control_host_reboot_script"):
            logger.warning(
                "control_host_reboot_script not defined, "
                "skip rebooting control host"
            )
            return
        logger.info("Rebooting control host")
        for cmd in self.config["control_host_reboot_script"]:
            logger.info("Running %s", cmd)
            try:
                subprocess.check_call(cmd.split(), timeout=60)
            except Exception as e:
                raise ProvisioningError("fail to reboot control host") from e

        logger.info("Rebooting DUT")
        self.hardreset()

        reboot_timeout = self.config.get("control_host_reboot_timeout", 120)
        time.sleep(reboot_timeout)
        # It should be up after 120s, but wait for another cycle if necessary
        for _ in range(int(reboot_timeout / 10)):
            try:
                self._run_control("true")
                break
            except ProvisioningError:
                logger.info("Waiting for control host to become active...")
            time.sleep(10)
        # One final check to ensure the control host is alive, or fail
        self._run_control("true")

    @contextmanager
    def _storage_plug_to_self(self):
        """Temporarily connect storage to provision an image.

        This context manager yields the block device path for the
        connected storage. After the context manager exits, the
        storage device will be re-connected to the DUT.
        """
        media = self.job_data["provision_data"].get("media")

        if media is None:
            cmd = self.config.get("control_switch_local_cmd", "stm -ts")
            self._run_control(cmd)
            try:
                yield self.config["test_device"]
            finally:
                return_cmd = self.config.get(
                    "control_switch_device_cmd", "stm -dut"
                )
                self._run_control(return_cmd)
        else:
            # If media option is provided, then DUT is probably capable of
            # booting from different media, we should switch both of them
            # to TS side regardless of which one was previously used
            # FIXME: Specify exception instead of `Exception`
            with contextlib.suppress(Exception):
                cmd = "zapper sdwire plug_to_self"
                sd_node = self._run_control(cmd)
            # FIXME: Specify exception instead of `Exception`
            with contextlib.suppress(Exception):
                cmd = "zapper typecmux plug_to_self"
                usb_node = self._run_control(cmd)

            if media == "sd":
                try:
                    yield sd_node.decode()
                finally:
                    self._run_control("zapper sdwire set DUT")
            elif media == "usb":
                try:
                    yield usb_node.decode()
                finally:
                    self._run_control("zapper typecmux set DUT")
            else:
                raise ProvisioningError(
                    'The "media" value in the "provision_data" section of '
                    'your job_data must be either "sd" or "usb", '
                    f"but got {media!r}"
                )

    def __check_rpyc_server_on_host(self, host: str) -> None:
        """
        Check if the host has an active RPyC server running.

        :raises ConnectionError in case the server is not reachable.
        """
        try:
            self._run_control("zapper --help")
            logger.debug("The host %s has an available RPyC server", host)
        except ProvisioningError as e:
            raise ConnectionError from e

    def provision(self):
        # If this is not a zapper, reboot before provisioning
        if "zapper" not in self.config.get("control_switch_local_cmd", ""):
            self.reboot_sdwire()
            time.sleep(5)
        else:
            _, control_host = self.get_credentials()
            logger.info(
                "Waiting for a running RPyC server on host %s", control_host
            )
            try:
                DefaultDevice.wait_online(
                    self.__check_rpyc_server_on_host, control_host, 60
                )
            except TimeoutError as e:
                raise ProvisioningError(
                    "Cannot reach out the service over RPyC"
                ) from e

        # determine where to get the provisioning image from
        source = self.job_data["provision_data"].get("url")
        if source is None:
            image_name = self.job_data["provision_data"].get("use_attachment")
            if image_name is None:
                raise ProvisioningError(
                    'In the "provision_data" section of your job_data '
                    'you must provide a value for "url" to specify '
                    "where to download an image from or a value for "
                    '"use_attachment" to specify which attachment to use '
                    "as an image"
                )
            source = Path.cwd() / ATTACHMENTS_DIR / "provision" / image_name
            if not source.exists():
                raise ProvisioningError(
                    'In the "provision_data" section of your job_data '
                    'you have provided a value for "use_attachment" but '
                    f"that attachment doesn't exist: {image_name}"
                )

        with self._storage_plug_to_self() as block_device:
            self.test_device = block_device
            self.flash_test_image(source)

            if self.job_data["provision_data"].get("create_user", True):
                with self.remote_mount():
                    image_type = self.get_image_type()
                    logger.info("Image type detected: %s", image_type)
                    logger.info("Creating Test User")
                    self.create_user(image_type)
            else:
                logger.info("Skipping test user creation (create_user=False)")

            self.run_post_provision_script()

        logger.info("Booting Test Image")
        self.hardreset()
        self.check_test_image_booted()

    def download(self, url: str, local: Path, timeout: Optional[int]):
        with requests.Session() as session:
            response = session.get(url, stream=True, timeout=timeout)
            response.raise_for_status()
            with open(local, "wb") as file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:  # filter out keep-alive new chunks
                        file.write(chunk)

    def transfer_test_image(self, local: Path, timeout: Optional[int] = None):
        ssh_options = " ".join(self.get_ssh_options())
        control_user, control_host = self.get_credentials()
        cmd = (
            "set -o pipefail; "
            f"cat {local} | "
            f"ssh {ssh_options} {control_user}@{control_host} "
            f'"zstdcat | sudo dd of={self.test_device} bs=16M"'
        )
        try:
            subprocess.run(
                cmd,
                capture_output=True,
                check=True,
                text=True,
                shell=True,
                executable="/bin/bash",
                timeout=timeout,
            )
        except subprocess.CalledProcessError as error:
            raise ProvisioningError(
                f"Error while piping the test image to {self.test_device} "
                f"through {control_user}@{control_host}: {error}"
            ) from error
        except subprocess.TimeoutExpired as error:
            raise ProvisioningError(
                f"Timeout while piping the test image to {self.test_device} "
                f"through {control_user}@{control_host} "
                f"using a timeout of {timeout}: {error}"
            ) from error

    def flash_test_image(self, source: Union[str, Path]):
        """Flash the image at :source to the sd card.

        :param source:
            URL or Path to retrieve the image from
        :raises ProvisioningError:
            If the command times out or anything else fails.
        """
        # First unmount, just in case
        self.unmount_writable_partition()

        if isinstance(source, Path):
            # the source is an existing attachment
            logger.info(
                "Flashing Test image %s on %s", source, self.test_device
            )
            self.transfer_test_image(local=source, timeout=1200)
        else:
            # the source is a URL
            with tempfile.NamedTemporaryFile(delete=True) as source_file:
                logger.info("Downloading test image from %s", source)
                self.download(source, local=source_file.name, timeout=1200)
                url_name = Path(urllib.parse.urlparse(source).path).name
                logger.info(
                    "Flashing Test image %s on %s", url_name, self.test_device
                )
                self.transfer_test_image(local=source_file.name, timeout=1800)

        try:
            self._run_control("sync")
        except Exception:
            # Nothing should go wrong here, but let's sleep if it does
            logger.warning("Something went wrong with the sync, sleeping...")
            time.sleep(30)
        try:
            self._run_control(
                "sudo hdparm -z {}".format(self.test_device),
                timeout=40,
            )
        except Exception as error:
            raise ProvisioningError(
                "Unable to run hdparm to rescan partitions"
            ) from error

    def _get_part_labels(self):
        lsblk_data = self._run_control(
            "lsblk -o NAME,LABEL -J {}".format(self.test_device)
        )
        lsblk_json = json.loads(lsblk_data.decode())
        # List of (name, label) pairs
        return [
            (x.get("name"), self.mount_point / x.get("label"))
            for x in lsblk_json["blockdevices"][0]["children"]
            if x.get("name") and x.get("label")
        ]

    @contextmanager
    def remote_mount(self):
        mount_list = self._get_part_labels()
        # Sometimes the labels don't show up to lsblk right away
        if not mount_list:
            print("No valid partitions found, retrying...")
            time.sleep(10)
            mount_list = self._get_part_labels()
        for dev, mount in mount_list:
            try:
                self._run_control(
                    "sudo mkdir -p {}".format(shlex.quote(str(mount)))
                )
                self._run_control(
                    "sudo mount /dev/{} {}".format(
                        dev, shlex.quote(str(mount))
                    )
                )
            except Exception:
                # If unmountable or any other error, go on to the next one
                mount_list.remove((dev, mount))
                continue
        try:
            yield self.mount_point
        finally:
            for _, mount in mount_list:
                self._run_control(
                    "sudo umount {}".format(shlex.quote(str(mount)))
                )

    def hardreset(self):
        """Reboot the device.

        :raises RecoveryError:
            If the command times out or anything else fails.

        .. note::
            This function runs the commands specified in 'reboot_script'
            in the config yaml.
        """
        for cmd in self.config.get("reboot_script", []):
            logger.info("Running %s", cmd)
            try:
                subprocess.check_call(cmd.split(), timeout=120)
            except Exception as e:
                raise RecoveryError("timeout reaching control host!") from e

    def get_image_type(self):
        """Figure out which kind of image is on the configured block device.

        :returns:
            image type as a string
        """

        def check_path(dir_path):
            self._run_control("test -e {}".format(dir_path))

        # First check if this is a ce-oem-iot image and type
        res = self.check_ce_oem_iot_image()
        if res:
            return res

        try:
            disk_info_path = (
                self.mount_point / "writable/lib/firmware/*-tegra*/"
            )
            self._run_control(f"ls {disk_info_path} &>/dev/null")
            return "tegra"
        except ProvisioningError:
            # Not a tegra image
            pass

        for path, img_type in self.IMAGE_PATH_IDS.items():
            try:
                full_path = self.mount_point / path
                check_path(full_path)
                return img_type
            except Exception:
                logger.warning(
                    "Path %s was not found, continue trying others", full_path
                )
                continue
        # We have no idea what kind of image this is
        return "unknown"

    def check_ce_oem_iot_image(self) -> bool:
        """Determine if this is a ce-oem-iot image.

        These images will have a .disk/info file with a buildstamp in it
        that looks like:
        iot-$project-$series-classic-(server|desktop)-$buildId
        """
        try:
            disk_info_path = self.mount_point / "writable/.disk/info"
            buildstamp = (
                r'"iot-[a-z]+-[a-z-]*(classic-(server|desktop)-\K[0-9]+'
            )
            buildstamp += r'|core-\K[0-9]+)"'
            release = self._run_control(
                f"grep -oP {buildstamp} {disk_info_path}"
            ).decode()
            release = int(release)
            if release > 2000:
                if release >= 2404:
                    return "ce-oem-iot-24-and-beyond"
                else:
                    return "ce-oem-iot-before-24"
            else:
                if release >= 24:
                    return "ce-oem-iot-24-and-beyond"
                else:
                    return "ce-oem-iot-before-24"
        except ProvisioningError:
            return False

    def unmount_writable_partition(self):
        try:
            self._run_control(
                "sudo umount {}*".format(self.test_device),
                timeout=30,
            )
        except KeyError as err:
            raise RecoveryError("Device config missing test_device") from err
        except Exception:
            # We might not be mounted, so expect this to fail sometimes
            logger.warning("Device %s might not be mounted", self.test_device)

    def create_user(self, image_type):
        """Create user account for default ubuntu user."""
        base = self.mount_point
        remote_tmp = Path("/tmp") / self.agent_name  # noqa: S108
        try:
            data_path = Path(__file__).parent / "../../data/muxpi"
            if image_type == "ce-oem-iot-before-24":
                self._run_control("mkdir -p {}".format(remote_tmp))
                self._copy_to_control(
                    data_path / "ce-oem-iot/user-data", remote_tmp
                )
                cmd = f"sudo cp {remote_tmp}/user-data {base}/system-boot/"
                self._run_control(cmd)
                self._configure_sudo()
            if image_type == "ce-oem-iot-24-and-beyond":
                self._run_control("mkdir -p {}".format(remote_tmp))
                self._copy_to_control(
                    data_path / "ce-oem-iot/user-data", remote_tmp
                )
                cmd = f"sudo cp {remote_tmp}/user-data {base}/writable"
                cmd += "/var/lib/cloud/seed/nocloud"
                self._run_control(cmd)
                self._configure_sudo()
            if image_type == "tegra":
                base = self.mount_point / "writable"
                ci_path = base / "var/lib/cloud/seed/nocloud"
                self._run_control(f"sudo mkdir -p {ci_path}")
                self._run_control(f"mkdir -p {remote_tmp}")
                self._copy_to_control(
                    data_path / "classic/user-data", remote_tmp
                )
                cmd = f"sudo cp {remote_tmp}/user-data {ci_path}"
                self._run_control(cmd)

                # Set grub timeouts to 0 to workaround reboot getting stuck
                # if spurious input is received on serial
                cmd = (
                    "sudo sed -i 's/timeout=[0-9]*/timeout=0/g' "
                    f"{base}/boot/grub/grub.cfg"
                )
                self._run_control(cmd)
                cmd = (
                    f"grep -rl 'GRUB_TIMEOUT=' {base}/etc/default/ | xargs "
                    "sudo sed -i 's/GRUB_TIMEOUT=[0-9]*/GRUB_TIMEOUT=0/g'"
                )
                self._run_control(cmd)

                self._configure_sudo()
                return
            if image_type == "pi-desktop":
                # make a spot to scp files to
                self._run_control("mkdir -p {}".format(remote_tmp))
                version_id_path = f"{base}/writable/etc/os-release"
                version = self._run_control(
                    f"grep '^VERSION_ID=' {version_id_path} | cut -d= -f2 | tr"
                    " -d '\"'"
                ).decode()
                major_version = version.split(".")[0]
                if major_version >= "25":
                    # For pi-desktop 25.04 and later, we use cloud-init
                    # to create the user
                    base = self.mount_point / "writable"
                    ci_path = base / "var/lib/cloud/seed/nocloud-net"
                    self._run_control(f"sudo mkdir -p {ci_path}")
                    self._run_control(f"mkdir -p {remote_tmp}")
                    self._copy_to_control(
                        data_path / "pi-desktop-plucky/meta-data", remote_tmp
                    )
                    cmd = f"sudo cp {remote_tmp}/meta-data {ci_path}"
                    self._run_control(cmd)
                    self._copy_to_control(
                        data_path / "pi-desktop-plucky/user-data", remote_tmp
                    )
                    cmd = f"sudo cp {remote_tmp}/user-data {ci_path}"
                    self._run_control(cmd)
                    # This needs to be removed for rpi, else
                    # cloud-init won't find the user-data we give it
                    cloud_cfg = (
                        base / "etc/cloud/cloud.cfg.d/99-fake?cloud.cfg"
                    )
                    rm_cmd = f"sudo rm -f {cloud_cfg}"
                    self._run_control(rm_cmd)

                else:
                    # For pi-desktop versions earlier than 25.04
                    # override oem-config
                    self._copy_to_control(
                        data_path / "pi-desktop/oem-config.service", remote_tmp
                    )

                    src_service = f"{remote_tmp}/oem-config.service"
                    dst_service = (
                        self.mount_point
                        / "writable/etc/systemd/system/oem-config.service"
                    )
                    cmd = f"sudo cp {src_service} {dst_service}"
                    self._run_control(cmd)

                    # Copy the preseed
                    self._copy_to_control(
                        data_path / "pi-desktop/preseed.cfg", remote_tmp
                    )
                    src_preseed = f"{remote_tmp}/preseed.cfg"
                    dst_preseed = self.mount_point / "writable/preseed.cfg"
                    cmd = f"sudo cp {src_preseed} {dst_preseed}"
                    self._run_control(cmd)

                # Make sure NetworkManager is started
                cmd = (
                    "sudo cp -a "
                    "{}/writable/etc/systemd/system/multi-user.target.wants"
                    "/NetworkManager.service "
                    "{}/writable/etc/systemd/system/"
                    "oem-config.target.wants".format(
                        self.mount_point, self.mount_point
                    )
                )
                self._run_control(cmd)

                self._configure_sudo()
                return
            if image_type == "core20":
                base = self.mount_point / "ubuntu-seed"
                ci_path = base / "data/etc/cloud/cloud.cfg.d"
                self._run_control(f"sudo mkdir -p {ci_path}")
                self._run_control("mkdir -p {}".format(remote_tmp))
                self._copy_to_control(
                    data_path / "uc20/99_nocloud.cfg", remote_tmp
                )
                cmd = f"sudo cp {remote_tmp}/99_nocloud.cfg {ci_path}"
                self._run_control(cmd)
            else:
                # For core or ubuntu classic images
                base = self.mount_point / "writable"
                if image_type == "core":
                    base = base / "system-data"
                if image_type == "ubuntu-cpc":
                    base = self.mount_point / "cloudimg-rootfs"
                ci_path = base / "var/lib/cloud/seed/nocloud-net"
                self._run_control(f"sudo mkdir -p {ci_path}")
                self._run_control("mkdir -p {}".format(remote_tmp))
                self._copy_to_control(
                    data_path / "classic/meta-data", remote_tmp
                )
                cmd = f"sudo cp {remote_tmp}/meta-data {ci_path}"
                self._run_control(cmd)
                self._copy_to_control(
                    data_path / "classic/user-data", remote_tmp
                )
                cmd = f"sudo cp {remote_tmp}/user-data {ci_path}"
                self._run_control(cmd)
                if image_type == "ubuntu":
                    # This needs to be removed on classic for rpi, else
                    # cloud-init won't find the user-data we give it
                    rm_cmd = "sudo rm -f {}".format(
                        base / "etc/cloud/cloud.cfg.d/99-fake?cloud.cfg"
                    )
                    self._run_control(rm_cmd)
        except Exception as e:
            raise ProvisioningError("Error creating user files") from e

    def _configure_sudo(self):
        # Setup sudoers data
        sudo_data = "ubuntu ALL=(ALL) NOPASSWD:ALL"
        sudo_path = "{}/writable/etc/sudoers.d/ubuntu".format(self.mount_point)
        self._run_control(
            "sudo bash -c \"echo '{}' > {}\"".format(sudo_data, sudo_path)
        )

    def check_test_image_booted(self):
        logger.info("Checking if test image booted.")
        started = time.time()
        # Retry for a while since we might still be rebooting
        test_username = self.job_data.get("test_data", {}).get(
            "test_username", "ubuntu"
        )
        test_password = self.job_data.get("test_data", {}).get(
            "test_password", "ubuntu"
        )

        boot_check_url = self.job_data.get("provision_data", {}).get(
            "boot_check_url", None
        )
        if boot_check_url is not None:
            # We don't support full shell expansion of the URL, but just
            # replace a literal $DEVICE_IP to the device's IP address
            boot_check_url = boot_check_url.replace(
                "$DEVICE_IP", self.config["device_ip"]
            )

        while time.time() - started < 1200:
            time.sleep(10)

            if boot_check_url is not None:
                logger.info(
                    "Checking %s to confirm boot success ...", boot_check_url
                )
                try:
                    with urllib.request.urlopen(
                        boot_check_url, timeout=5
                    ) as response:
                        if response.status == 200:
                            return True
                        logger.info(
                            "Check returned %d, expecting 200", response.status
                        )
                except urllib.error.URLError as e:
                    logger.info("Boot check failed with %s", e)

            else:
                device_ip = self.config["device_ip"]
                cmd = [
                    "sshpass",
                    "-p",
                    test_password,
                    "ssh-copy-id",
                    *self.get_ssh_options(),
                    f"{test_username}@{device_ip}",
                ]
                try:
                    subprocess.check_output(
                        cmd, stderr=subprocess.STDOUT, timeout=60
                    )
                    return True
                except subprocess.CalledProcessError as e:
                    logger.info("ssh-id-copy failed with %s", e)
                except subprocess.TimeoutExpired as e:
                    logger.info("ssh-id-copy timed out after %s", e)

        # If we get here, then we didn't boot in time
        raise ProvisioningError("Failed to boot test image!")

    def run_post_provision_script(self):
        # Run post provision commands on control host if there are any, but
        # don't fail the provisioning step if any of them don't work
        for cmd in self.config.get("post_provision_script", []):
            logger.info("Running %s", cmd)
            try:
                self._run_control(cmd)
            except Exception:
                logger.warning("Error running %s", cmd)
