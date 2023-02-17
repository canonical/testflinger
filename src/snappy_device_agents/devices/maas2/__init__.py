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

"""Ubuntu MaaS 2.x CLI support code."""

import logging

import yaml

import snappy_device_agents
from snappy_device_agents import logmsg
from snappy_device_agents.devices import (
    DefaultDevice,
    ProvisioningError,
    RecoveryError,
    SerialLogger,
    catch,
)
from snappy_device_agents.devices.maas2.maas2 import Maas2

device_name = "maas2"


class DeviceAgent(DefaultDevice):

    """Tool for provisioning baremetal with a given image."""

    @catch(RecoveryError, 46)
    def provision(self, args):
        """Method called when the command is invoked."""
        with open(args.config) as configfile:
            config = yaml.safe_load(configfile)
        snappy_device_agents.configure_logging(config)
        device = Maas2(args.config, args.job_data)
        logmsg(logging.INFO, "BEGIN provision")
        logmsg(logging.INFO, "Provisioning device")
        serial_host = config.get("serial_host")
        serial_port = config.get("serial_port")
        serial_proc = SerialLogger(
            serial_host, serial_port, "provision-serial.log"
        )
        serial_proc.start()
        try:
            device.provision()
        except ProvisioningError as e:
            logmsg(logging.ERROR, "Provisioning failed: {}".format(str(e)))
            return 1
        except Exception as e:
            raise e
        finally:
            serial_proc.stop()
        logmsg(logging.INFO, "END provision")
