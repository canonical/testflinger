# Copyright (C) 2018 Canonical
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

"""Ubuntu OEM Recovery Provisioner support code."""

import json
import logging
import subprocess
import time
import yaml

from devices import (ProvisioningError,
                     RecoveryError)
from snappy_device_agents import TimeoutError

logger = logging.getLogger()


class OemRecovery:

    """Device Agent for OEM Recovery."""

    def __init__(self, config, job_data):
        with open(config) as configfile:
            self.config = yaml.load(configfile)
        with open(job_data) as j:
            self.job_data = json.load(j)

    def _run_device(self, cmd, timeout=60):
        """
        Run a command on the control host over ssh

        :param cmd:
            Command to run
        :param timeout:
            Timeout (default 60)
        :returns:
            Return output from the command, if any
        """
        device_ip = self.config.get('device_ip')
        try:
            test_username = self.job_data.get(
                'test_data').get('test_username', 'ubuntu')
        except:
            test_username = 'ubuntu'
        ssh_cmd = ['ssh', '-o', 'StrictHostKeyChecking=no',
                   '-o', 'UserKnownHostsFile=/dev/null',
                   '{}@{}'.format(test_username, self.config['device_ip']),
                   cmd]
        try:
            output = subprocess.check_output(
                ssh_cmd, stderr=subprocess.STDOUT, timeout=timeout)
        except subprocess.CalledProcessError as e:
            raise ProvisioningError(e.output)
        return output

    def provision(self):
        """Provision the device"""

        # First, ensure the device is online and reachable
        try:
            self.copy_ssh_id()
        except subprocess.CalledProcessError:
            self.hardreset()
            self.check_device_booted()

        logger.info('Recovering OEM image')
        recovery_cmds = self.config.get('recovery_cmds')
        self._run_cmd_list(recovery_cmds)
        self.check_device_booted()

    def copy_ssh_id(self):
        try:
            test_username = self.job_data.get(
                'test_data').get('test_username', 'ubuntu')
            test_password = self.job_data.get(
                'test_data').get('test_password', 'ubuntu')
        except:
            test_username = 'ubuntu'
            test_password = 'ubuntu'
        cmd = ['sshpass', '-p', test_password, 'ssh-copy-id',
               '-o', 'StrictHostKeyChecking=no',
               '-o', 'UserKnownHostsFile=/dev/null',
               '{}@{}'.format(test_username, self.config['device_ip'])]
        subprocess.check_output(
            cmd, stderr=subprocess.STDOUT, timeout=60)

    def check_device_booted(self):
        logger.info("Checking to see if the device is available.")
        started = time.time()
        # Wait for provisioning to complete - can take a very long time
        while time.time() - started < 3600:
            try:
                time.sleep(90)
                self.copy_ssh_id()
                return True
            except Exception:
                pass
        # If we get here, then we didn't boot in time
        agent_name = self.config.get('agent_name')
        logger.error('Device %s unreachable,  provisioning'
                     'failed!', agent_name)
        raise ProvisioningError("Failed to boot test image!")

    def _run_cmd_list(self, cmdlist):
        """
        Run a list of commands

        :param cmdlist:
            List of commands to run
        """
        if not cmdlist:
            return
        for cmd in cmdlist:
            logger.info("Running %s", cmd)
            try:
                output = self._run_device(cmd, timeout=90)
            except TimeoutError:
                raise ProvisioningError("timeout reaching control host!")
            logger.info(output)

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
            except Exception:
                raise RecoveryError("timeout reaching control host!")
