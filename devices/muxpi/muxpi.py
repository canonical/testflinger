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

"""Ubuntu Raspberry PI muxpi support code."""

import json
import logging
import multiprocessing
import os
import subprocess
import time
import yaml

import snappy_device_agents

from devices import (ProvisioningError,
                     RecoveryError)

logger = logging.getLogger()


class MuxPi:

    """Device Agent for MuxPi."""

    def __init__(self, config, job_data):
        with open(config) as configfile:
            self.config = yaml.safe_load(configfile)
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
            snappy_device_agents.download(url, 'snappy.img')
        except KeyError:
            raise ProvisioningError('You must specify a "url" value in '
                                    'the "provision_data" section of '
                                    'your job_data')
        self._run_control('stm -ts')
        time.sleep(5)
        logger.info('Flashing Test image')
        image_file = snappy_device_agents.compress_file('snappy.img')
        server_ip = snappy_device_agents.get_local_ip_addr()
        serve_q = multiprocessing.Queue()
        file_server = multiprocessing.Process(
            target=snappy_device_agents.serve_file,
            args=(serve_q, image_file,))
        file_server.start()
        server_port = serve_q.get()
        try:
            self.flash_test_image(server_ip, server_port)
            file_server.terminate()
            logger.info("Creating Test User")
            self.create_user()
            logger.info("Booting Test Image")
            self.unmount_writable_partition()
            self._run_control('stm -dut')
            self.check_test_image_booted()
        except Exception:
            raise

    def flash_test_image(self, server_ip, server_port):
        """
        Flash the image at :image_url to the sd card.

        :param server_ip:
            IP address of the image server. The image will be downloaded and
            uncompressed over the SD card.
        :param server_port:
            TCP port to connect to on server_ip for downloading the image
        :raises ProvisioningError:
            If the command times out or anything else fails.
        """
        # First unmount, just in case
        self.unmount_writable_partition()
        cmd = 'nc.traditional {} {}| xzcat| sudo dd of={} bs=16M'.format(
            server_ip, server_port, self.config['test_device'])
        logger.info("Running: %s", cmd)
        try:
            # XXX: I hope 30 min is enough? but maybe not!
            self._run_control(cmd, timeout=1800)
        except Exception:
            raise ProvisioningError("timeout reached while flashing image!")
        try:
            self._run_control('sync')
        except Exception:
            # Nothing should go wrong here, but let's sleep if it does
            logger.warn("Something went wrong with the sync, sleeping...")
            time.sleep(30)
        try:
            self._run_control(
                'sudo hdparm -z {}'.format(self.config['test_device']),
                timeout=30)
        except Exception:
            raise ProvisioningError("Unable to run hdparm to rescan "
                                    "partitions")

    def unmount_writable_partition(self):
        try:
            self._run_control(
                'sudo umount {}*'.format(self.config['test_device']),
                timeout=30)
        except KeyError:
            raise RecoveryError("Device config missing test_device")
        except Exception:
            # We might not be mounted, so expect this to fail sometimes
            pass

    def mount_writable_partition(self):
        # Mount the writable partition
        try:
            self._run_control('sudo mount {} /mnt'.format(
                              self.config['snappy_writable_partition']))
        except KeyError:
            raise RecoveryError(
                "Device config missing snappy_writable_partition")
        except Exception:
            err = ("Error mounting writable partition on test image {}. "
                   "Check device configuration".format(
                       self.config['snappy_writable_partition']))
            raise ProvisioningError(err)

    def create_user(self):
        """Create user account for default ubuntu user"""
        self.mount_writable_partition()
        metadata = 'instance_id: cloud-image'
        userdata = ('#cloud-config\n'
                    'password: ubuntu\n'
                    'chpasswd:\n'
                    '    list:\n'
                    '        - ubuntu:ubuntu\n'
                    '    expire: False\n'
                    'ssh_pwauth: True')
        try:
            output = self._run_control('ls /mnt')
            if 'system-data' in str(output):
                base = '/mnt/system-data'
            else:
                base = '/mnt'
            cloud_path = os.path.join(
                base, 'var/lib/cloud/seed/nocloud-net')
            self._run_control('sudo mkdir -p {}'.format(cloud_path))
            write_cmd = "sudo bash -c \"echo '{}' > /{}/{}\""
            self._run_control(
                write_cmd.format(metadata, cloud_path, 'meta-data'))
            self._run_control(
                write_cmd.format(userdata, cloud_path, 'user-data'))
        except Exception:
            raise ProvisioningError("Error creating user files")

    def check_test_image_booted(self):
        logger.info("Checking if test image booted.")
        started = time.time()
        # Retry for a while since we might still be rebooting
        test_username = self.job_data.get(
            'test_data').get('test_username', 'ubuntu')
        test_password = self.job_data.get(
            'test_data').get('test_password', 'ubuntu')
        while time.time() - started < 600:
            try:
                time.sleep(10)
                cmd = ['sshpass', '-p', test_password, 'ssh-copy-id',
                       '-o', 'StrictHostKeyChecking=no',
                       '-o', 'UserKnownHostsFile=/dev/null',
                       '{}@{}'.format(test_username, self.config['device_ip'])]
                subprocess.check_output(
                    cmd, stderr=subprocess.STDOUT, timeout=60)
                return True
            except Exception:
                pass
        # If we get here, then we didn't boot in time
        raise ProvisioningError("Failed to boot test image!")
