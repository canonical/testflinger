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

import guacamole
import imp
import logging
import os
import snappy_device_agents
import yaml


class ProvisioningError(Exception):
    pass


class RecoveryError(Exception):
    pass


class DefaultRuntest(guacamole.Command):

    """Tool for running tests on a provisioned device."""

    def invoked(self, ctx):
        """Method called when the command is invoked."""
        with open(ctx.args.config) as configfile:
            config = yaml.safe_load(configfile)
        snappy_device_agents.configure_logging(config)
        snappy_device_agents.logmsg(logging.INFO, "BEGIN testrun")

        test_opportunity = snappy_device_agents.get_test_opportunity(
            ctx.args.job_data)
        test_cmds = test_opportunity.get('test_data').get('test_cmds')
        exitcode = snappy_device_agents.run_test_cmds(test_cmds, config)
        snappy_device_agents.logmsg(logging.INFO, "END testrun")
        return exitcode

    def register_arguments(self, parser):
        """Method called to customize the argument parser."""
        parser.add_argument('-c', '--config', required=True,
                            help='Config file for this device')
        parser.add_argument('job_data', help='Testflinger json data file')


def Catch(exception, returnval=0):
    """ Decorator for catching Exceptions and returning values instead

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
    devs = [os.path.join(device_path, device)
            for device in os.listdir(device_path)
            if os.path.isdir(os.path.join(device_path, device))]
    for device in devs:
        if '__pycache__' in device:
            continue
        module = imp.load_source(
            'module', os.path.join(device, '__init__.py'))
        devices.append((module.device_name, module.DeviceAgent))
    return tuple(devices)


if __name__ == '__main__':
    load_devices()
