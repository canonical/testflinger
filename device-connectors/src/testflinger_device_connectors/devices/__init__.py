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

import contextlib
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
from typing import Callable, Optional

import yaml

import testflinger_device_connectors
from testflinger_device_connectors.fw_devices.firmware_update import (
    FirmwareUpdateError,
    LVFSDevice,
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
    """Generate real or fake SerialLogger object based on params."""
    if host and port and filename:
        return RealSerialLogger(host, port, filename)
    return StubSerialLogger(host, port, filename)


class StubSerialLogger:
    """Fake SerialLogger when we don't have Serial Logger data defined."""

    def __init__(self, host, port, filename):
        pass

    def start(self):
        pass

    def stop(self):
        pass


class RealSerialLogger:
    """Real SerialLogger for when we have a serial logging service."""

    def __init__(self, host, port, filename):
        """Set up a subprocess to connect to an ip and collect serial logs."""
        self.host = host
        self.port = int(port)
        self.filename = filename

    def start(self):
        """Start the serial logger connection."""

        def reconnector():
            """Reconnect when needed."""
            while True:
                try:
                    self._log_serial()
                except Exception:
                    logger.error("Error connecting to serial logging server")

                # Keep trying if we can't connect, but sleep between attempts
                time.sleep(30)

        self.proc = multiprocessing.Process(target=reconnector, daemon=True)
        self.proc.start()

    def _log_serial(self):
        """Log data to the serial data to the output file."""
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
        """Stop the serial logger."""
        self.proc.terminate()


class DefaultDevice:
    """Defines a common class for all DeviceConnector to use default methods.

    Attributes:
        config: Configuration with all the information of the device.
    """

    def __init__(self, config: dict) -> None:
        """Initialize class with device config and writing data to JSON file.

        :param config: Dict with all the information relevant to a device.
        """
        self.config = config
        self.write_device_info()

    def write_device_info(self) -> None:
        """Write device information to device-info.json using the config
        stored during initialization.
        """
        device_info = {
            "device_info": {
                field: value
                for field in ("device_ip", "agent_name")
                if (value := self.config.get(field))
            }
        }
        with open("device-info.json", "w", encoding="utf-8") as devinfo_file:
            devinfo_file.write(json.dumps(device_info))

    def firmware_update(self, args):
        """Process firmware update commands (default method)."""
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
        username = test_opportunity.get("test_data", {}).get(
            "test_username", "ubuntu"
        )
        exitcode = 0
        lvfs_supported_version = ["latest"]

        try:
            target_device = detect_device(device_ip, username, config)
            # For LVFS, only update to latest is supported
            if (
                isinstance(target_device, LVFSDevice)
                and version not in lvfs_supported_version
            ):
                raise FirmwareUpdateError(
                    "Fail to provide version in firmware_update_data. "
                    f"Current supported version: {lvfs_supported_version}"
                )
            target_device.get_fw_info()
            reboot_required = (
                target_device.upgrade()
                if version == "latest"
                else target_device.downgrade(version)
            )
            if reboot_required:
                target_device.reboot()
                if not target_device.check_results():
                    raise FirmwareUpdateError(
                        "The firmware version did not update successfully"
                    )
        except FirmwareUpdateError as e:
            logger.error("Firmware Update failed: %s", str(e))
            exitcode = 1
        finally:
            logger.info("END firmware_update")
        if ignore_failure:
            exitcode = 0
        return exitcode

    def runtest(self, args):
        """Process test commands (default method)."""
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

    def allocate(self):
        """Allocate devices for multi-agent jobs (default method)."""
        pass

    def import_ssh_key(self, key: str, keyfile: str = "key.pub") -> None:
        """Import SSH key provided in Reserve data.

        :param key: SSH key to import.
        :param keyfile: Output file where to store the imported key
        :raises RuntimeError: If failure during import ssh keys
        """
        cmd = ["ssh-import-id", "-o", keyfile, key]
        for retry in range(10):
            try:
                subprocess.run(
                    cmd,
                    timeout=30,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    check=True,
                )
                logger.info("Successfully imported key: %s", key)
                break

            except subprocess.TimeoutExpired:
                pass
            except subprocess.CalledProcessError as exc:
                output = (exc.stdout or b"").decode()
                if "status_code=404" in output:
                    raise RuntimeError(
                        f"Failed to import ssh key: {key}. User not found."
                    ) from exc

            logger.error("Unable to import ssh key from: %s", key)
            logger.info("Retrying...")
            time.sleep(min(2**retry, 100))
        else:
            raise RuntimeError(
                f"Failed to import ssh key: {key}. Maximum retries reached"
            )

    def copy_ssh_key(
        self,
        device_ip: str,
        username: str,
        password: Optional[str] = None,
        key: Optional[str] = None,
    ):
        """If provided, copy the SSH `key` to the DUT,
        otherwise copy the agent's using password authentication.

        :raises RuntimeError in case it can't copy the SSH keys
        """
        if not key and not password:
            raise ValueError("Cannot copy the agent's SSH key w/o password")

        if password:
            cmd = ["sshpass", "-p", password]
        else:
            cmd = []

        cmd.extend(["ssh-copy-id", "-f"])

        if key:
            cmd.extend(["-i", key])

        cmd.extend(
            [
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "UserKnownHostsFile=/dev/null",
                "{}@{}".format(username, device_ip),
            ]
        )

        for _retry in range(10):
            # Retry ssh key copy just in case it's rebooting
            try:
                subprocess.check_call(cmd, timeout=30)
                break
            except (
                subprocess.CalledProcessError,
                subprocess.TimeoutExpired,
            ):
                logger.error("Error copying ssh key to device for: %s", key)
                logger.info("Retrying...")
                time.sleep(60)

        else:
            logger.error("Failed to copy ssh key: %s", key)
            raise RuntimeError

    def reserve(self, args):
        """Reserve systems (default method)."""
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
            with contextlib.suppress(FileNotFoundError):
                os.unlink("key.pub")

            try:
                # Import SSH Keys with ssh-import-id
                self.import_ssh_key(key, keyfile="key.pub")

                # Attempt to copy keys only if import succeeds
                with contextlib.suppress(RuntimeError):
                    self.copy_ssh_key(device_ip, test_username, key="key.pub")
            except RuntimeError as exc:
                logger.error(exc)

        # default reservation timeout is 1 hour
        timeout = int(reserve_data.get("timeout", "3600"))
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
        now = datetime.now().astimezone().isoformat()
        expire_time = (
            datetime.now().astimezone() + timedelta(seconds=timeout)
        ).isoformat()
        print("Current time:           [{}]".format(now))
        print("Reservation expires at: [{}]".format(expire_time))
        print(
            "Reservation will automatically timeout in {} seconds".format(
                timeout
            )
        )
        job_id = job_data.get("job_id", "<job_id>")
        print(
            "To end the reservation sooner use: "
            + "testflinger-cli cancel {}".format(job_id)
        )
        time.sleep(int(timeout))

    def cleanup(self, _):
        """Clean up devices (default method)."""
        pass


def get_device_stage_func(device: str, stage: str, config: dict) -> Callable:
    """Load the selected device connector and
    return the selected stage method.
    """
    module = import_module(f".{device}", package=__package__)
    device_class = module.DeviceConnector
    device_instance = device_class(config=config)
    stage_method = getattr(device_instance, stage)
    return stage_method
