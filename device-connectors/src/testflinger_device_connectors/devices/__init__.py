# Copyright (C) 2015-2024 Canonical
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>

import json
import logging
import multiprocessing
import os
import select
import socket
import subprocess
import time
from datetime import datetime, timedelta
from importlib import import_module
from typing import Callable

import yaml

import testflinger_device_connectors
from testflinger_device_connectors.fw_devices.firmware_update import (
    detect_device,
)

logger = logging.getLogger(__name__)


DEVICE_CONNECTORS = (
    "cm3",
    "dell_oemscript",
    "dragonboard",
    "fake_connector",
    "hp_oemscript",
    "lenovo_oemscript",
    "oem_autoinstall",
    "maas2",
    "multi",
    "muxpi",
    "netboot",
    "noprovision",
    "oemrecovery",
    "oemscript",
    "zapper_iot",
    "zapper_kvm",
)


class ProvisioningError(Exception):
    pass


class RecoveryError(Exception):
    pass


def SerialLogger(host=None, port=None, filename=None):
    """
    Factory to generate real or fake SerialLogger object based on params
    """
    if host and port and filename:
        return RealSerialLogger(host, port, filename)
    return StubSerialLogger(host, port, filename)


class StubSerialLogger:
    """Fake SerialLogger when we don't have Serial Logger data defined"""

    def __init__(self, host, port, filename):
        pass

    def start(self):
        pass

    def stop(self):
        pass


class RealSerialLogger:
    """Real SerialLogger for when we have a serial logging service"""

    def __init__(self, host, port, filename):
        """Set up a subprocess to connect to an ip and collect serial logs"""
        self.host = host
        self.port = int(port)
        self.filename = filename

    def start(self):
        """Start the serial logger connection"""

        def reconnector():
            """Reconnect when needed"""
            while True:
                try:
                    self._log_serial()
                except Exception:
                    pass
                # Keep trying if we can't connect, but sleep between attempts
                logger.error("Error connecting to serial logging server")
                time.sleep(30)

        self.proc = multiprocessing.Process(target=reconnector, daemon=True)
        self.proc.start()

    def _log_serial(self):
        """Log data to the serial data to the output file"""
        with open(self.filename, "ab+") as f:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((self.host, self.port))
                logger.info("Successfully connected to serial logging server")
                while True:
                    read_sockets, _, _ = select.select([s], [], [])
                    for sock in read_sockets:
                        data = sock.recv(4096)
                        if data:
                            f.write(data)
                            f.flush()
                        else:
                            logger.error(
                                "Serial log connection closed - attempts to "
                                "reconnect will be made in the background"
                            )
                            return

    def stop(self):
        """Stop the serial logger"""
        self.proc.terminate()


class DefaultDevice:
    def firmware_update(self, args):
        """Default method for processing firmware update commands"""
        with open(args.config) as configfile:
            config = yaml.safe_load(configfile)
        logger.info("BEGIN firmware_update")

        test_opportunity = testflinger_device_connectors.get_test_opportunity(
            args.job_data
        )
        fw_config = test_opportunity.get("firmware_update_data")
        ignore_failure = fw_config.get("ignore_failure", False)
        version = fw_config.get("version")
        device_ip = config["device_ip"]
        target_device_username = "ubuntu"
        exitcode = 0
        supported_version = ["latest"]

        if version not in supported_version:
            logger.info(
                "Fail to provide version in firmware_update_data. "
                + "Current supported version: latest",
            )
            exitcode = 1
        else:
            try:
                target_device = detect_device(
                    device_ip, target_device_username
                )
                target_device.get_fw_info()
                if version == "latest":
                    reboot_required = target_device.upgrade()
                if reboot_required:
                    target_device.reboot()
                    update_succeeded = target_device.check_results()
                    if not update_succeeded:
                        exitcode = 1
            except Exception as err:
                logger.error("Firmware Update failed: ", str(err))
                exitcode = 1
            finally:
                logger.info("END firmware_update")
        if ignore_failure:
            exitcode = 0
        return exitcode

    def runtest(self, args):
        """Default method for processing test commands"""
        with open(args.config) as configfile:
            config = yaml.safe_load(configfile)
        logger.info("BEGIN testrun")

        test_opportunity = testflinger_device_connectors.get_test_opportunity(
            args.job_data
        )
        test_cmds = test_opportunity.get("test_data").get("test_cmds")
        serial_host = config.get("serial_host")
        serial_port = config.get("serial_port")
        serial_proc = SerialLogger(serial_host, serial_port, "test-serial.log")
        serial_proc.start()

        extra_env = {}
        extra_env["AGENT_NAME"] = config.get("agent_name", "")
        extra_env["REBOOT_SCRIPT"] = ";".join(config.get("reboot_script", ""))
        if "env" not in config:
            config["env"] = {}
        config["env"].update(extra_env)
        try:
            exitcode = testflinger_device_connectors.run_test_cmds(
                test_cmds, config
            )
        except Exception as e:
            raise e
        finally:
            serial_proc.stop()
        logger.info("END testrun")
        return exitcode

    def allocate(self, args):
        """Default method for allocating devices for multi-agent jobs"""
        with open(args.config) as configfile:
            config = yaml.safe_load(configfile)
        device_ip = config["device_ip"]
        device_info = {"device_info": {"device_ip": device_ip}}
        print(device_info)
        with open("device-info.json", "w", encoding="utf-8") as devinfo_file:
            devinfo_file.write(json.dumps(device_info))

    def reserve(self, args):
        """Default method for reserving systems"""
        with open(args.config) as configfile:
            config = yaml.safe_load(configfile)
        logger.info("BEGIN reservation")
        job_data = testflinger_device_connectors.get_test_opportunity(
            args.job_data
        )
        try:
            test_username = job_data["test_data"]["test_username"]
        except KeyError:
            test_username = "ubuntu"
        device_ip = config["device_ip"]
        reserve_data = job_data["reserve_data"]
        ssh_keys = reserve_data.get("ssh_keys", [])
        for key in ssh_keys:
            try:
                os.unlink("key.pub")
            except FileNotFoundError:
                pass
            cmd = ["ssh-import-id", "-o", "key.pub", key]
            proc = subprocess.run(cmd)
            if proc.returncode != 0:
                logger.error("Unable to import ssh key from: %s", key)
                continue
            cmd = [
                "ssh-copy-id",
                "-f",
                "-i",
                "key.pub",
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "UserKnownHostsFile=/dev/null",
                "{}@{}".format(test_username, device_ip),
            ]
            for retry in range(10):
                # Retry ssh key copy just in case it's rebooting
                try:
                    proc = subprocess.run(cmd, timeout=30)
                    if proc.returncode == 0:
                        break
                except subprocess.TimeoutExpired:
                    # Log an error for timeout or any other problem
                    pass
                logger.error("Error copying ssh key to device for: %s", key)
                if retry != 9:
                    logger.info("Retrying...")
                    time.sleep(60)
                else:
                    logger.error("Failed to copy ssh key: %s", key)
        # default reservation timeout is 1 hour
        timeout = int(reserve_data.get("timeout", "3600"))
        # If max_reserve_timeout isn't specified, default to 6 hours
        max_reserve_timeout = int(
            config.get("max_reserve_timeout", 6 * 60 * 60)
        )
        if timeout > max_reserve_timeout:
            timeout = max_reserve_timeout
        serial_host = config.get("serial_host")
        serial_port = config.get("serial_port")
        print("*** TESTFLINGER SYSTEM RESERVED ***")
        print("You can now connect to {}@{}".format(test_username, device_ip))
        if serial_host and serial_port:
            print(
                "Serial access is available via: telnet {} {}".format(
                    serial_host, serial_port
                )
            )
        now = datetime.utcnow().isoformat()
        expire_time = (
            datetime.utcnow() + timedelta(seconds=timeout)
        ).isoformat()
        print("Current time:           [{}]".format(now))
        print("Reservation expires at: [{}]".format(expire_time))
        print(
            "Reservation will automatically timeout in {} "
            "seconds".format(timeout)
        )
        job_id = job_data.get("job_id", "<job_id>")
        print(
            "To end the reservation sooner use: testflinger-cli "
            "cancel {}".format(job_id)
        )
        time.sleep(int(timeout))

    def cleanup(self, _):
        """Default method for cleaning up devices"""
        pass


def get_device_stage_func(device: str, stage: str) -> Callable:
    """
    Load the selected device connector and return the selected stage method
    """
    module = import_module(f".{device}", package=__package__)
    device_class = getattr(module, "DeviceConnector")
    device_instance = device_class()
    stage_method = getattr(device_instance, stage)
    return stage_method
