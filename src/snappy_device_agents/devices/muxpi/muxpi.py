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

import json
import logging
import multiprocessing
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

import yaml

import snappy_device_agents
from snappy_device_agents.devices import ProvisioningError, RecoveryError

logger = logging.getLogger()


class MuxPi:

    """Device Agent for MuxPi."""

    IMAGE_PATH_IDS = {
        "writable/usr/bin/firefox": "pi-desktop",
        "writable/etc": "ubuntu",
        "writable/system-data": "core",
        "ubuntu-seed/snaps": "core20",
        "cloudimg-rootfs/etc/cloud/cloud.cfg": "ubuntu-cpc",
    }

    def __init__(self, config, job_data):
        with open(config) as configfile:
            self.config = yaml.safe_load(configfile)
        with open(job_data) as j:
            self.job_data = json.load(j)
        self.agent_name = self.config.get("agent_name")
        self.mount_point = Path("/mnt") / self.agent_name

    def _run_control(self, cmd, timeout=60):
        """
        Run a command on the control host over ssh

        :param cmd:
            Command to run
        :param timeout:
            Timeout (default 60)
        :returns:
            Return output from the command, if any
        """
        control_host = self.config.get("control_host")
        control_user = self.config.get("control_user", "ubuntu")
        ssh_cmd = [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "{}@{}".format(control_user, control_host),
            cmd,
        ]
        try:
            output = subprocess.check_output(
                ssh_cmd, stderr=subprocess.STDOUT, timeout=timeout
            )
        except subprocess.CalledProcessError as e:
            raise ProvisioningError(e.output)
        return output

    def _copy_to_control(self, local_file, remote_file):
        """
        Copy a file to the control host over ssh

        :param local_file:
            Local filename
        :param remote_file:
            Remote filename
        """
        control_host = self.config.get("control_host")
        control_user = self.config.get("control_user", "ubuntu")
        ssh_cmd = [
            "scp",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            local_file,
            "{}@{}:{}".format(control_user, control_host, remote_file),
        ]
        try:
            output = subprocess.check_output(ssh_cmd, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            raise ProvisioningError(e.output)
        return output

    def provision(self):
        try:
            url = self.job_data["provision_data"]["url"]
            snappy_device_agents.download(url, "snappy.img")
        except KeyError:
            raise ProvisioningError(
                'You must specify a "url" value in '
                'the "provision_data" section of '
                "your job_data"
            )
        cmd = self.config.get("control_switch_local_cmd", "stm -ts")
        self._run_control(cmd)
        time.sleep(5)
        logger.info("Flashing Test image")
        image_file = snappy_device_agents.compress_file("snappy.img")
        server_ip = snappy_device_agents.get_local_ip_addr()
        serve_q = multiprocessing.Queue()
        file_server = multiprocessing.Process(
            target=snappy_device_agents.serve_file,
            args=(
                serve_q,
                image_file,
            ),
        )
        file_server.start()
        server_port = serve_q.get()
        try:
            self.flash_test_image(server_ip, server_port)
            file_server.terminate()
            with self.remote_mount():
                image_type = self.get_image_type()
                logger.info("Creating Test User")
                self.create_user(image_type)
            self.run_post_provision_script()
            logger.info("Booting Test Image")
            cmd = self.config.get("control_switch_device_cmd", "stm -dut")
            self._run_control(cmd)
            self.hardreset()
            self.check_test_image_booted()
        except Exception:
            raise

    def flash_test_image(self, server_ip, server_port):
        """
        Flash the image at :image_url to the sd card.

        :param server_ip:
            IP address of the image server. The image will be downloaded and
            uncompressed over the SD card.
        :param server_port:
            TCP port to connect to on server_ip for downloading the image
        :raises ProvisioningError:
            If the command times out or anything else fails.
        """
        # First unmount, just in case
        self.unmount_writable_partition()
        cmd = "nc.traditional {} {}| xzcat| sudo dd of={} bs=16M".format(
            server_ip, server_port, self.config["test_device"]
        )
        logger.info("Running: %s", cmd)
        try:
            # XXX: I hope 30 min is enough? but maybe not!
            self._run_control(cmd, timeout=1800)
        except Exception:
            raise ProvisioningError("timeout reached while flashing image!")
        try:
            self._run_control("sync")
        except Exception:
            # Nothing should go wrong here, but let's sleep if it does
            logger.warn("Something went wrong with the sync, sleeping...")
            time.sleep(30)
        try:
            self._run_control(
                "sudo hdparm -z {}".format(self.config["test_device"]),
                timeout=30,
            )
        except Exception:
            raise ProvisioningError(
                "Unable to run hdparm to rescan " "partitions"
            )

    def _get_part_labels(self):
        test_device = self.config["test_device"]
        lsblk_data = self._run_control(
            "lsblk -o NAME,LABEL -J {}".format(test_device)
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
                self._run_control("sudo mkdir -p {}".format(mount))
                self._run_control("sudo mount /dev/{} {}".format(dev, mount))
            except Exception:
                # If unmountable or any other error, go on to the next one
                mount_list.remove((dev, mount))
                continue
        try:
            yield self.mount_point
        finally:
            for _, mount in mount_list:
                self._run_control("sudo umount {}".format(mount))

    def hardreset(self):
        """
        Reboot the device.

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
            except Exception:
                raise RecoveryError("timeout reaching control host!")

    def get_image_type(self):
        """
        Figure out which kind of image is on the configured block device

        :returns:
            image type as a string
        """

        def check_path(dir):
            self._run_control("test -e {}".format(dir))

        # First check if this is a limerick image
        try:
            disk_info_path = self.mount_point / "writable/.disk/info"
            self._run_control(f"grep limerick {disk_info_path}")
            return "limerick"
        except ProvisioningError:
            # Not a limerick image
            pass

        for path, img_type in self.IMAGE_PATH_IDS.items():
            try:
                path = self.mount_point / path
                check_path(path)
                logger.info("Image type detected: {}".format(img_type))
                return img_type
            except Exception:
                # Path was not found, continue trying others
                continue
        # We have no idea what kind of image this is
        return "unknown"

    def unmount_writable_partition(self):
        try:
            self._run_control(
                "sudo umount {}*".format(self.config["test_device"]),
                timeout=30,
            )
        except KeyError:
            raise RecoveryError("Device config missing test_device")
        except Exception:
            # We might not be mounted, so expect this to fail sometimes
            pass

    def create_user(self, image_type):
        """Create user account for default ubuntu user"""
        metadata = "instance_id: cloud-image"
        userdata = (
            "#cloud-config\n"
            "password: ubuntu\n"
            "chpasswd:\n"
            "    list:\n"
            "        - ubuntu:ubuntu\n"
            "    expire: False\n"
            "ssh_pwauth: True"
        )
        # For core20:
        uc20_ci_data = (
            "#cloud-config\n"
            "datasource_list: [ NoCloud, None ]\n"
            "datasource:\n"
            "  NoCloud:\n"
            "    user-data: |\n"
            "      #cloud-config\n"
            "      password: ubuntu\n"
            "      chpasswd:\n"
            "          list:\n"
            "              - ubuntu:ubuntu\n"
            "          expire: False\n"
            "      ssh_pwauth: True\n"
            "    meta-data: |\n"
            "      instance_id: cloud-image"
        )

        base = self.mount_point
        remote_tmp = Path("/tmp") / self.agent_name
        try:
            data_path = Path(__file__).parent / "../../data"
            if image_type == "limerick":
                self._copy_to_control(
                    data_path / "limerick/user-data", remote_tmp
                )
                cmd = f"sudo cp {remote_tmp}/user-data {base}/system-boot/"
                self._run_control(cmd)
            if image_type == "pi-desktop":
                # make a spot to scp files to
                self._run_control("mkdir -p {}".format(remote_tmp))

                # Override oem-config so that it uses the preseed
                self._copy_to_control(
                    data_path / "pi-desktop/oem-config.service", remote_tmp
                )
                cmd = (
                    "sudo cp {}/oem-config.service "
                    "{}/writable/lib/systemd/system/"
                    "oem-config.service".format(remote_tmp, self.mount_point)
                )
                self._run_control(cmd)

                # Copy the preseed
                self._copy_to_control(
                    data_path / "pi-desktop/preseed.cfg", remote_tmp
                )
                cmd = "sudo cp {}/preseed.cfg {}/writable/preseed.cfg".format(
                    remote_tmp, self.mount_point
                )
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

                # Setup sudoers data
                sudo_data = "ubuntu ALL=(ALL) NOPASSWD:ALL"
                sudo_path = "{}/writable/etc/sudoers.d/ubuntu".format(
                    self.mount_point
                )
                self._run_control(
                    "sudo bash -c \"echo '{}' > {}\"".format(
                        sudo_data, sudo_path
                    )
                )
                return
            if image_type == "core20":
                base = self.mount_point / "ubuntu-seed"
                ci_path = base / "data/etc/cloud/cloud.cfg.d"
                self._run_control("sudo mkdir -p {}".format(ci_path))
                write_cmd = "sudo bash -c \"echo '{}' > /{}/{}\""
                self._run_control(
                    write_cmd.format(uc20_ci_data, ci_path, "99_nocloud.cfg")
                )
            else:
                # For core or ubuntu classic images
                base = self.mount_point / "writable"
                if image_type == "core":
                    base = base / "system-data"
                if image_type == "ubuntu-cpc":
                    base = self.mount_point / "cloudimg-rootfs"
                ci_path = base / "var/lib/cloud/seed/nocloud-net"
                self._run_control("sudo mkdir -p {}".format(ci_path))
                write_cmd = "sudo bash -c \"echo '{}' > /{}/{}\""
                self._run_control(
                    write_cmd.format(metadata, ci_path, "meta-data")
                )
                self._run_control(
                    write_cmd.format(userdata, ci_path, "user-data")
                )
                if image_type == "ubuntu":
                    # This needs to be removed on classic for rpi, else
                    # cloud-init won't find the user-data we give it
                    rm_cmd = "sudo rm -f {}".format(
                        base / "etc/cloud/cloud.cfg.d/99-fake?cloud.cfg"
                    )
                    self._run_control(rm_cmd)
        except Exception:
            raise ProvisioningError("Error creating user files")

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
        while time.time() - started < 1200:
            try:
                time.sleep(10)
                cmd = [
                    "sshpass",
                    "-p",
                    test_password,
                    "ssh-copy-id",
                    "-o",
                    "StrictHostKeyChecking=no",
                    "-o",
                    "UserKnownHostsFile=/dev/null",
                    "{}@{}".format(test_username, self.config["device_ip"]),
                ]
                subprocess.check_output(
                    cmd, stderr=subprocess.STDOUT, timeout=60
                )
                return True
            except Exception:
                pass
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
                logger.warn("Error running %s", cmd)
