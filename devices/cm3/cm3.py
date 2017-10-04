# Copyright (C) 2017 Canonical
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

"""Ubuntu Raspberry PI cm3 support code."""

import json
import logging
import subprocess
import time
import yaml

from devices import (ProvisioningError,
                     RecoveryError)

logger = logging.getLogger()


class CM3:

    """Device Agent for CM3."""

    def __init__(self, config, job_data):
        with open(config) as configfile:
            self.config = yaml.load(configfile)
        with open(job_data) as j:
            self.job_data = json.load(j)

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
        control_host = self.config.get('control_host')
        control_user = self.config.get('control_user', 'ubuntu')
        ssh_cmd = ['ssh', '-o', 'StrictHostKeyChecking=no',
                   '-o', 'UserKnownHostsFile=/dev/null',
                   '{}@{}'.format(control_user, control_host),
                   cmd]
        try:
            output = subprocess.check_output(
                ssh_cmd, stderr=subprocess.STDOUT, timeout=timeout)
        except subprocess.CalledProcessError as e:
            raise ProvisioningError(e.output)
        return output

    def provision(self):
        try:
            url = self.job_data['provision_data']['url']
        except KeyError:
            raise ProvisioningError('You must specify a "url" value in '
                                    'the "provision_data" section of '
                                    'your job_data')
        self._run_control('sudo pi3gpio set high 16')
        time.sleep(5)
        self.hardreset()
        logger.info('Flashing image')
        out = self._run_control('sudo cm3-installer {}'.format(url),
                                timeout=900)
        logger.info(out)
        self._run_control('sudo sync')
        time.sleep(5)
        out = self._run_control('sudo udisksctl power-off -b /dev/sda ')
        logger.info(out)
        time.sleep(5)
        self._run_control('sudo pi3gpio set low 16')
        time.sleep(5)
        self.hardreset()
        if self.check_test_image_booted():
            return
        agent_name = self.config.get('agent_name')
        logger.error('Device %s unreachable after provisioning, deployment '
                     'failed!', agent_name)
        raise ProvisioningError("Provisioning failed!")

    def check_test_image_booted(self):
        logger.info("Checking if test image booted.")
        started = time.time()
        # Retry for a while since we might still be rebooting
        test_username = self.job_data.get(
            'test_data').get('test_username', 'ubuntu')
        test_password = self.job_data.get(
            'test_data').get('test_password', 'ubuntu')
        while time.time() - started < 300:
            try:
                time.sleep(10)
                cmd = ['sshpass', '-p', test_password, 'ssh-copy-id',
                       '-o', 'StrictHostKeyChecking=no',
                       '-o', 'UserKnownHostsFile=/dev/null',
                       '{}@{}'.format(test_username, self.config['device_ip'])]
                subprocess.check_output(
                    cmd, stderr=subprocess.STDOUT, timeout=60)
                return True
            except:
                pass
        # If we get here, then we didn't boot in time
        raise ProvisioningError("Failed to boot test image!")

    def hardreset(self):
        """
        Reboot the device.

        :raises RecoveryError:
            If the command times out or anything else fails.

        .. note::
            This function runs the commands specified in 'reboot_script'
            in the config yaml.
        """
        for cmd in self.config['reboot_script']:
            logger.info("Running %s", cmd)
            try:
                subprocess.check_call(cmd.split(), timeout=60)
            except:
                raise RecoveryError("timeout reaching control host!")
