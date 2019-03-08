# Copyright (C) 2016 Canonical
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

"""Dragonboard support code."""

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


class Dragonboard:

    """Snappy Device Agent for Dragonboard."""

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
        cmd = ['ssh', '-o', 'StrictHostKeyChecking=no',
               '-o', 'UserKnownHostsFile=/dev/null',
               'linaro@{}'.format(self.config['device_ip']),
               cmd]
        try:
            output = subprocess.check_output(
                cmd, stderr=subprocess.STDOUT, timeout=timeout)
        except subprocess.CalledProcessError as e:
            raise ProvisioningError(e.output)
        return output

    def setboot(self, mode):
        """
        Set the boot mode of the device.

        :param mode:
            One of 'master' or 'test'
        :raises ProvisioningError:
            If the command times out or anything else fails.

        This method sets the snappy boot method to the specified value.
        """
        if mode == 'master':
            setboot_script = self.config['select_master_script']
        elif mode == 'test':
            setboot_script = self.config['select_test_script']
        else:
            raise KeyError
        for cmd in setboot_script:
            logger.info("Running %s", cmd)
            try:
                subprocess.check_call(cmd.split(), timeout=60)
            except:
                raise ProvisioningError("timeout reaching control host!")

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

    def ensure_test_image(self, test_username, test_password):
        """
        Actively switch the device to boot the test image.

        :param test_username:
            Username of the default user in the test image
        :param test_password:
            Password of the default user in the test image
        :raises ProvisioningError:
            If the command times out or anything else fails.
        """
        logger.info("Booting the test image")
        self.setboot('test')
        try:
            self._run_control('sudo /sbin/reboot')
        except:
            pass
        time.sleep(60)

        started = time.time()
        # Retry for a while since we might still be rebooting
        test_image_booted = False
        while time.time() - started < 300:
            try:
                time.sleep(10)
                cmd = ['sshpass', '-p', test_password, 'ssh-copy-id',
                       '-o', 'StrictHostKeyChecking=no',
                       '-o', 'UserKnownHostsFile=/dev/null',
                       '{}@{}'.format(test_username, self.config['device_ip'])]
                subprocess.check_call(cmd)
                test_image_booted = self.is_test_image_booted()
            except:
                pass
            if test_image_booted:
                break
        # Check again if we are in the master image
        if not test_image_booted:
            raise ProvisioningError("Failed to boot test image!")

    def is_test_image_booted(self):
        """
        Check if the master image is booted.

        :returns:
            True if the test image is currently booted, False otherwise.
        :raises TimeoutError:
            If the command times out
        :raises CalledProcessError:
            If the command fails
        """
        logger.info("Checking if test image booted.")
        cmd = ['ssh', '-o', 'StrictHostKeyChecking=no',
               '-o', 'UserKnownHostsFile=/dev/null',
               'ubuntu@{}'.format(self.config['device_ip']),
               'snap -h']
        try:
            subprocess.check_output(
                cmd, stderr=subprocess.STDOUT, timeout=60)
        except:
            return False
        # If we get here, then the above command proved we are in snappy
        return True

    def is_master_image_booted(self):
        """
        Check if the master image is booted.

        :returns:
            True if the master image is currently booted, False otherwise.

        .. note::
            The master image is used for writing a new image to local media
        """
        # FIXME: come up with a better way of checking this
        logger.info("Checking if master image booted.")
        try:
            output = self._run_control('cat /etc/issue')
        except:
            logger.info("Error checking device state. Forcing reboot...")
            return False
        if 'Debian GNU' in str(output):
            return True
        return False

    def ensure_master_image(self):
        """
        Actively switch the device to boot the test image.

        :raises RecoveryError:
            If the command times out or anything else fails.
        """
        logger.info("Making sure the master image is booted")

        # most likely, we are still in a test image, check that first
        test_booted = self.is_test_image_booted()

        if test_booted:
            # We are not in the master image, so just hard reset
            self.setboot('master')
            self.hardreset()

            started = time.time()
            while time.time() - started < 300:
                time.sleep(10)
                master_booted = self.is_master_image_booted()
                if master_booted:
                    return
            # Check again if we are in the master image
            if not master_booted:
                raise RecoveryError("Could not reboot to master!")

        master_booted = self.is_master_image_booted()
        if not master_booted:
            logging.warn(
                "Device is in an unknown state, attempting to recover")
            self.hardreset()
            started = time.time()
            while time.time() - started < 300:
                time.sleep(10)
                if self.is_master_image_booted():
                    return
                elif self.is_test_image_booted():
                    # device was stuck, but booted to the test image
                    # So rerun ourselves to get to the master image
                    return self.ensure_master_image()
            # timeout reached, this could be a dead device
            raise RecoveryError(
                "Device is in an unknown state, may require manual recovery!")
        # If we get here, the master image was already booted, so just return

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
        try:
            self._run_control(
                'sudo umount {}*'.format(self.config['test_device']),
                timeout=30)
        except ProvisioningError:
            # We might not be mounted, so expect this to fail sometimes
            pass
        cmd = 'nc {} {}| unxz| sudo dd of={} bs=16M'.format(
            server_ip, server_port, self.config['test_device'])
        logger.info("Running: %s", cmd)
        try:
            # XXX: I hope 30 min is enough? but maybe not!
            self._run_control(cmd, timeout=1800)
        except:
            raise ProvisioningError("timeout reached while flashing image!")
        try:
            self._run_control('sync')
        except:
            # Nothing should go wrong here, but let's sleep if it does
            logger.warn("Something went wrong with the sync, sleeping...")
            time.sleep(30)
        try:
            self._run_control(
                'sudo hdparm -z {}'.format(self.config['test_device']),
                timeout=30)
        except:
            raise ProvisioningError("Unable to run hdparm to rescan "
                                    "partitions")

    def mount_writable_partition(self):
        # Mount the writable partition
        try:
            self._run_control('sudo mount {} /mnt'.format(
                              self.config['snappy_writable_partition']))
        except:
            err = ("Error mounting writable partition on test image {}. "
                   "Check device configuration".format(
                       self.config['snappy_writable_partition']))
            raise ProvisioningError(err)

    def create_extrausers(self):
        """Create extrauser account for default ubuntu user"""
        self.mount_writable_partition()
        try:
            self._run_control('sudo mkdir -p /mnt/user-data/ubuntu')
            self._run_control('sudo chown 1000.1000 /mnt/user-data/ubuntu')
        except:
            raise ProvisioningError("Error creating user home dir")
        try:
            self._run_control('sudo mkdir -p /mnt/system-data/var/lib/')
        except:
            raise ProvisioningError("Error creating dir for user files")
        userdata_path = os.path.normpath(
            os.path.join(os.path.dirname(os.path.realpath(__file__)),
                         '..', '..', 'data', 'extrausers'))
        cmd = ['scp', '-r', '-o', 'StrictHostKeyChecking=no',
               '-o', 'UserKnownHostsFile=/dev/null', userdata_path,
               'linaro@{}:/tmp/'.format(
                   self.config['device_ip'])]
        try:
            subprocess.check_call(cmd, timeout=60)
            self._run_control(
                'sudo cp -a /tmp/extrausers /mnt/system-data/var/lib/')
        except:
            raise ProvisioningError("Error writing user files")

    def setup_sudo(self):
        sudo_data = 'ubuntu ALL=(ALL) NOPASSWD:ALL'
        sudo_path = '/mnt/system-data/etc/sudoers.d/ubuntu'
        self._run_control(
            'sudo mkdir -p {}'.format(os.path.dirname(sudo_path)))
        self._run_control(
            'sudo bash -c "echo \'{}\' > {}"'.format(sudo_data, sudo_path))

    def wipe_test_device(self):
        """Safety check - wipe the test drive if things go wrong

        This way if we reboot the sytem after a failed provision, it goes
        back to the control boot image which we could use to provision
        something else.
        """
        try:
            test_device = self.config['test_device']
            logger.error("Failed to write image, cleaning up...")
            self._run_control(
                'sudo sgdisk -o {}'.format(test_device))
        except:
            # This is an attempt to salvage a bad run, further tracebacks
            # would just add to the noise
            pass

    def provision(self):
        """Provision the device"""
        url = self.job_data['provision_data'].get('url')
        if url:
            snappy_device_agents.download(url, 'snappy.img')
        else:
            try:
                model_assertion = self.config['model_assertion']
                channel = self.job_data['provision_data']['channel']
                extra_snaps = self.job_data.get(
                    'provision_data').get('extra-snaps', [])
                cmd = ['sudo', 'ubuntu-image', '-c', channel,
                       model_assertion, '-o', 'snappy.img']
                for snap in extra_snaps:
                    cmd.append('--extra-snaps')
                    cmd.append(snap)
                subprocess.check_output(cmd, stderr=subprocess.STDOUT)
            except Exception:
                logger.exception("Bad data passed for provisioning")
                raise ProvisioningError("Error copying system-user assertion")
        image_file = snappy_device_agents.compress_file('snappy.img')
        test_username = self.job_data.get(
            'test_data').get('test_username', 'ubuntu')
        test_password = self.job_data.get(
            'test_data').get('test_password', 'ubuntu')
        server_ip = snappy_device_agents.get_local_ip_addr()
        serve_q = multiprocessing.Queue()
        file_server = multiprocessing.Process(
            target=snappy_device_agents.serve_file,
            args=(serve_q, image_file,))
        file_server.start()
        server_port = serve_q.get()
        logger.info("Flashing Test Image")
        try:
            self.flash_test_image(server_ip, server_port)
            file_server.terminate()
            logger.info("Creating Test User")
            self.create_extrausers()
            self.setup_sudo()
            logger.info("Booting Test Image")
            self.ensure_test_image(test_username, test_password)
        except:
            # wipe out whatever we installed if things go badly
            self.wipe_test_device()
            raise
        logger.info("END provision")
