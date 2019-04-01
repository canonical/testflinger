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
import subprocess
import time
import yaml

from datetime import datetime, timedelta


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


class DefaultReserve(guacamole.Command):

    """Block this system while it is reserved for manual use"""

    def invoked(self, ctx):
        with open(ctx.args.config) as configfile:
            config = yaml.safe_load(configfile)
        snappy_device_agents.configure_logging(config)
        snappy_device_agents.logmsg(logging.INFO, "BEGIN reservation")
        job_data = snappy_device_agents.get_test_opportunity(
            ctx.args.job_data)
        try:
            test_username = job_data['test_data']['test_username']
        except KeyError:
            test_username = 'ubuntu'
        device_ip = config['device_ip']
        reserve_data = job_data['reserve_data']
        ssh_keys = reserve_data.get('ssh_keys', [])
        for key in ssh_keys:
            try:
                os.unlink('key.pub')
            except FileNotFoundError:
                pass
            cmd = ['ssh-import-id', '-o', 'key.pub', key]
            proc = subprocess.run(cmd)
            if proc.returncode != 0:
                print('Unable to import ssh key from:', key)
                continue
            cmd = ['ssh-copy-id', '-f', '-i', 'key.pub',
                   '{}@{}'.format(test_username, device_ip)]
            proc = subprocess.run(cmd)
            if proc.returncode != 0:
                print('Problem copying ssh key to target device for:', key)
        # default reservation timeout is 1 hour
        timeout = reserve_data.get('timeout', '3600')
        # If max_reserve_timeout isn't specified, default to 18 hours
        max_reserve_timeout = config.get('max_reserve_timeout', 18 * 60 * 60)
        if timeout > max_reserve_timeout:
            timeout = max_reserve_timeout
        print('*** TESTFLINGER SYSTEM RESERVED ***')
        print('You can now connect to {}@{}'.format(test_username, device_ip))
        now = datetime.utcnow().isoformat()
        expire_time = (datetime.utcnow() + timedelta(seconds=timeout)).isoformat()
        print('Current time:           [{}]'.format(now))
        print('Reservation expires at: [{}]'.format(expire_time))
        print('Reservation will automatically timeout in {} '
              'seconds'.format(timeout))
        job_id = job_data.get('job_id', '<job_id>')
        print('To end the reservation sooner use: testflinger-cli '
              'cancel {}'.format(job_id))
        time.sleep(int(timeout))

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
