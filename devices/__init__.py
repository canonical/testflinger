# Copyright (C) 2015 Canonical
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

import imp
import logging
import multiprocessing
import os
import select
import snappy_device_agents
import socket
import subprocess
import time
import yaml

from datetime import datetime, timedelta


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
        if not (host and port and filename):
            self.stub = True
        self.stub = False
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
                snappy_device_agents.logmsg(
                    logging.ERROR, "Error connecting to serial logging server"
                )
                time.sleep(30)

        self.proc = multiprocessing.Process(target=reconnector, daemon=True)
        self.proc.start()

    def _log_serial(self):
        """Log data to the serial data to the output file"""
        with open(self.filename, "a+") as f:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((self.host, self.port))
                while True:
                    read_sockets, _, _ = select.select([s], [], [])
                    for sock in read_sockets:
                        data = sock.recv(4096)
                        if data:
                            f.write(
                                data.decode(encoding="utf-8", errors="ignore")
                            )
                            f.flush()
                        else:
                            snappy_device_agents.logmsg(
                                logging.ERROR, "Serial Log connection closed"
                            )
                            return

    def stop(self):
        """Stop the serial logger"""
        self.proc.terminate()


class DefaultDevice:
    def runtest(self, args):
        """Default method for processing test commands"""
        with open(args.config) as configfile:
            config = yaml.safe_load(configfile)
        snappy_device_agents.configure_logging(config)
        snappy_device_agents.logmsg(logging.INFO, "BEGIN testrun")

        test_opportunity = snappy_device_agents.get_test_opportunity(
            args.job_data
        )
        test_cmds = test_opportunity.get("test_data").get("test_cmds")
        serial_host = config.get("serial_host")
        serial_port = config.get("serial_port")
        serial_proc = SerialLogger(serial_host, serial_port, "test-serial.log")
        serial_proc.start()
        try:
            exitcode = snappy_device_agents.run_test_cmds(test_cmds, config)
        except Exception as e:
            raise e
        finally:
            serial_proc.stop()
        snappy_device_agents.logmsg(logging.INFO, "END testrun")
        return exitcode

    def reserve(self, args):
        """Default method for reserving systems"""
        with open(args.config) as configfile:
            config = yaml.safe_load(configfile)
        snappy_device_agents.configure_logging(config)
        snappy_device_agents.logmsg(logging.INFO, "BEGIN reservation")
        job_data = snappy_device_agents.get_test_opportunity(args.job_data)
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
                snappy_device_agents.logmsg(
                    logging.ERROR,
                    "Unable to import ssh key from: {}".format(key),
                )
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
                snappy_device_agents.logmsg(
                    logging.ERROR,
                    "Error copying ssh key to device for: {}".format(key),
                )
                if retry != 9:
                    snappy_device_agents.logmsg(logging.INFO, "Retrying...")
                    time.sleep(60)
                else:
                    snappy_device_agents.logmsg(
                        logging.ERROR, "Failed to copy ssh key: {}".format(key)
                    )
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


def catch(exception, returnval=0):
    """Decorator for catching Exceptions and returning values instead

    This is useful because for certain things, like RecoveryError, we
    need to give the calling process a hint that we failed for that
    reason, so it can act accordingly, by disabling the device for example
    """

    def _wrapper(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exception:
                return returnval

        return wrapper

    return _wrapper


def load_devices():
    devices = []
    device_path = os.path.dirname(os.path.realpath(__file__))
    devs = [
        os.path.join(device_path, device)
        for device in os.listdir(device_path)
        if os.path.isdir(os.path.join(device_path, device))
    ]
    for device in devs:
        if "__pycache__" in device:
            continue
        module = imp.load_source("module", os.path.join(device, "__init__.py"))
        devices.append((module.device_name, module.DeviceAgent))
    return tuple(devices)


if __name__ == "__main__":
    load_devices()
