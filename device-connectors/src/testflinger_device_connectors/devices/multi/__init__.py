# Copyright (C) 2023 Canonical
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

"""Ubuntu multi-device support code."""

import json
import logging
import os
import yaml

import testflinger_device_connectors
from testflinger_device_connectors import logmsg
from testflinger_device_connectors.devices import (
    DefaultDevice,
    SerialLogger,
)
from testflinger_device_connectors.devices.multi.multi import Multi
from testflinger_device_connectors.devices.multi.tfclient import TFClient

device_name = "multi"


class DeviceConnector(DefaultDevice):

    """Device Connector for provisioning multiple devices at the same time"""

    def init_device(self, args):
        """Read config data and initialize the device object."""
        with open(args.config, encoding="utf-8") as configfile:
            self.config = yaml.safe_load(configfile)
        self.job_data = testflinger_device_connectors.get_test_opportunity(
            args.job_data
        )
        testflinger_device_connectors.configure_logging(self.config)
        testflinger_server = self.config.get("testflinger_server")
        tfclient = TFClient(testflinger_server)
        self.device = Multi(self.config, self.job_data, tfclient)

    def provision(self, args):
        """Method called when the command is invoked."""
        self.init_device(args)
        logmsg(logging.INFO, "BEGIN provision")
        logmsg(logging.INFO, "Provisioning device")
        self.device.provision()
        logmsg(logging.INFO, "END provision")

    def runtest(self, args):
        """
        The runtest method for multi-device connectors

        This is slightly different from the generic one because we also need
        to import the job_list.json data and inject the device_ip for each
        device into the environment
        """
        self.init_device(args)

        logmsg(logging.INFO, "BEGIN testrun")

        test_cmds = self.job_data.get("test_data").get("test_cmds")
        serial_host = self.config.get("serial_host")
        serial_port = self.config.get("serial_port")
        serial_proc = SerialLogger(serial_host, serial_port, "test-serial.log")
        serial_proc.start()

        # Inject the IPs for each device into the environment
        extra_env = self.get_device_ip_dict()
        if "env" not in self.config:
            self.config["env"] = {}
        self.config["env"].update(extra_env)

        try:
            exitcode = testflinger_device_connectors.run_test_cmds(
                test_cmds, self.config
            )
        except Exception as e:
            raise e
        finally:
            serial_proc.stop()
        testflinger_device_connectors.logmsg(logging.INFO, "END testrun")
        return exitcode

    def get_job_list_data(self, job_list_file: str = "job_list.json") -> list:
        """Read job_list.json and return the list data"""
        if not os.path.exists(job_list_file):
            logmsg(
                logging.ERROR,
                "Unable to find multi-job data file, job_list.json not found",
            )
            return []
        with open(job_list_file) as job_list_file:
            job_list_data = json.load(job_list_file)
        return job_list_data

    def get_device_ip_dict(self):
        """
        Read job_list.json and return a dict of device IPs like this that
        can be used in the environment for the test commands:
        {
            "DEVICE_IP_1": "10.1.1.1",
            "DEVICE_IP_2": "10.1.1.2"
        }
        """
        job_list_data = self.get_job_list_data()
        device_ip_dict = {}
        for i, job in enumerate(job_list_data):
            key = "DEVICE_IP_{}".format(i + 1)
            value = job.get("device_info", {}).get("device_ip")
            device_ip_dict[key] = value
        return device_ip_dict

    def cleanup(self, args):
        """Cancel all subordinates jobs before finishing the multi-agent job"""
        self.init_device(args)
        job_list_data = self.get_job_list_data()
        job_id_list = [job.get("job_id") for job in job_list_data]
        self.device.cancel_jobs(job_id_list)
