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

"""Ubuntu MaaS 2.x CLI support code."""

import base64
import json
import logging
import subprocess
import time
import yaml

from devices import (ProvisioningError,
                     RecoveryError)

logger = logging.getLogger()


class Maas2:

    """Device Agent for Maas2."""

    def __init__(self, config, job_data):
        with open(config) as configfile:
            self.config = yaml.safe_load(configfile)
        with open(job_data) as j:
            self.job_data = json.load(j)
        self.maas_user = self.config.get('maas_user')
        self.node_id = self.config.get('node_id')
        self.agent_name = self.config.get('agent_name')
        self.timeout_min = int(self.config.get('timeout_min', 60))

    def _logger_debug(self, message):
        logger.debug("MAAS: {}".format(message))

    def _logger_info(self, message):
        logger.info("MAAS: {}".format(message))

    def _logger_warning(self, message):
        logger.warning("MAAS: {}".format(message))

    def _logger_error(self, message):
        logger.error("MAAS: {}".format(message))

    def _logger_critical(self, message):
        logger.critical("MAAS: {}".format(message))

    def recover(self):
        self._logger_info("Releasing node {}".format(self.agent_name))
        self.node_release()

    def provision(self):
        # Check if this is a device where we need to clear the tpm (dawson)
        if self.config.get('clear_tpm'):
            self.clear_tpm()
        provision_data = self.job_data.get('provision_data')
        # Default to a safe LTS if no distro is specified
        distro = provision_data.get('distro', 'xenial')
        kernel = provision_data.get('kernel')
        user_data = provision_data.get('user_data')
        self.deploy_node(distro, kernel, user_data)

    def clear_tpm(self):
        self._logger_info("Clearing the TPM before provisioning")
        # First see if we can run the command on the current install
        if self._run_tpm_clear_cmd():
            return
        # If not, then deploy bionic and try again
        self.deploy_node()
        if not self._run_tpm_clear_cmd():
            raise ProvisioningError("Failed to clear TPM")

    def _run_tpm_clear_cmd(self):
        # Run the command to clear the tpm over ssh
        cmd = ['ssh', '-o', 'StrictHostKeyChecking=no',
               '-o', 'UserKnownHostsFile=/dev/null',
               'ubuntu@{}'.format(self.config['device_ip']),
               'echo 5 | sudo tee /sys/class/tpm/tpm0/ppi/request']
        try:
            subprocess.check_call(cmd, timeout=30)
            cmd = ['ssh', '-o', 'StrictHostKeyChecking=no',
                   '-o', 'UserKnownHostsFile=/dev/null',
                   'ubuntu@{}'.format(self.config['device_ip']),
                   'cat /sys/class/tpm/tpm0/ppi/request']
            output = subprocess.check_output(cmd, timeout=30)
            # If we now see "5" in that file, then clearing tpm succeeded
            if output.decode('utf-8').strip() == "5":
                return True
        except Exception:
            # Fall through if we fail for any reason
            pass
        return False

    def deploy_node(self, distro='bionic', kernel=None, user_data=None):
        # Deploy the node in maas, default to bionic if nothing is specified
        self._logger_info('Acquiring node')
        cmd = ['maas', self.maas_user, 'machines', 'allocate',
               'system_id={}'.format(self.node_id)]
        # Do not use runcmd for this - we need the output, not the end user
        subprocess.check_call(cmd)
        self._logger_info('Starting node {} '
                          'with distro {}'.format(self.agent_name, distro))
        cmd = ['maas', self.maas_user, 'machine', 'deploy', self.node_id,
               'distro_series={}'.format(distro)]
        if kernel:
            cmd.append('hwe_kernel={}'.format(kernel))
        if user_data:
            data = base64.b64encode(user_data.encode()).decode()
            cmd.append('user_data={}'.format(data))
        process = subprocess.run(cmd,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
        try:
            process.check_returncode()
        except subprocess.CalledProcessError:
            self._logger_error('maas-cli call failure happens.')
            raise ProvisioningError(process.stdout.decode())

        # Make sure the device is available before returning
        minutes_spent = 0
        self._logger_info("Timeout value: {} minutes.".format(
            self.timeout_min))
        while minutes_spent < self.timeout_min:
            time.sleep(60)
            minutes_spent += 1
            self._logger_info('{} minutes passed '
                              'since deployment.'.format(minutes_spent))
            status = self.node_status()

            if status == 'Failed deployment':
                self._logger_error('MaaS reports Failed Deployment')
                exception_msg = "Provisioning failed because " + \
                                "MaaS got unexpected or " + \
                                "deployment failure status signal."
                raise ProvisioningError(exception_msg)

            if status == 'Deployed':
                if self.check_test_image_booted():
                    self._logger_info('Deployed and booted.')
                    return

        self._logger_error('Device {} still in "{}" state, deployment '
                           'failed!'.format(self.agent_name, status))
        self._logger_error(process.stdout.decode())
        exception_msg = "Provisioning failed because deployment timeout. " + \
                        "Deploying for more than " + \
                        "{} minutes.".format(self.timeout_min)
        raise ProvisioningError(exception_msg)

    def check_test_image_booted(self):
        self._logger_info("Checking if test image booted.")
        cmd = ['ssh', '-o', 'StrictHostKeyChecking=no',
               '-o', 'UserKnownHostsFile=/dev/null',
               'ubuntu@{}'.format(self.config['device_ip']),
               '/bin/true']
        try:
            subprocess.check_output(
                cmd, stderr=subprocess.STDOUT, timeout=60)
        except Exception:
            return False
        # If we get here, then the above command proved we are booted
        return True

    def node_status(self):
        """Return status of the node according to maas:

        Ready: Node is unused
        Allocated: Node is allocated
        Deploying: Deployment in progress
        Deployed: Node is provisioned and ready for use
        """
        cmd = ['maas', self.maas_user, 'machine', 'read', self.node_id]
        # Do not use runcmd for this - we need the output, not the end user
        output = subprocess.check_output(cmd)
        data = json.loads(output.decode())
        return data.get('status_name')

    def node_release(self):
        """Release the node to make it available again"""
        cmd = ['maas', self.maas_user, 'machine', 'release', self.node_id]
        subprocess.run(cmd)
        # Make sure the device is available before returning
        for timeout in range(0, 10):
            time.sleep(5)
            status = self.node_status()
            if status == 'Ready':
                return
        self._logger_error('Device {} still in "{}" state, could not '
                           'recover!'.format(self.agent_name, status))
        raise RecoveryError("Device recovery failed!")
