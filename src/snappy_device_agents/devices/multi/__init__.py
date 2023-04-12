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
import yaml

import snappy_device_agents
from snappy_device_agents import logmsg
from snappy_device_agents.devices import (
    DefaultDevice,
    SerialLogger,
)
from snappy_device_agents.devices.multi.multi import Multi
from snappy_device_agents.devices.multi.tfclient import TFClient

device_name = "multi"


class DeviceAgent(DefaultDevice):

    """Device Agent for provisioning multiple devices at the same time"""

    def init_device(self, args):
        """Read config data and initialize the device object."""
        with open(args.config, encoding="utf-8") as configfile:
            self.config = yaml.safe_load(configfile)
        self.job_data = snappy_device_agents.get_test_opportunity(
            args.job_data
        )
        snappy_device_agents.configure_logging(self.config)
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
        The runtest method for multi-device agents

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
            exitcode = snappy_device_agents.run_test_cmds(
                test_cmds, self.config
            )
        except Exception as e:
            raise e
        finally:
            serial_proc.stop()
        snappy_device_agents.logmsg(logging.INFO, "END testrun")
        return exitcode

    def get_job_list_data(self):
        """Read job_list.json and return the data"""
        with open("job_list.json") as job_list_file:
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
