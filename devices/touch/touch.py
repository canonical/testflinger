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

"""Ubuntu Touch support code."""

import json
import logging
import yaml

from devices import (ProvisioningError,
                     RecoveryError)
from snappy_device_agents import download, runcmd

logger = logging.getLogger()


class Touch:

    """Device Agent for Touch."""

    def __init__(self, config, job_data):
        with open(config) as configfile:
            self.config = yaml.load(configfile)
        with open(job_data) as j:
            self.job_data = json.load(j)

    def recover(self):
        recovery_script = self.config.get('recovery_script')
        for cmd in recovery_script:
            logger.info("Running %s", cmd)
            rc = runcmd(cmd)
            if rc:
                raise RecoveryError("Device recovery failed!")

    def provision(self):
        p = self.job_data.get('provision_data')
        self.get_recovery_image()

        server = p.get('server', 'https://system-image.ubuntu.com')

        if p.get('revision'):
            rev_arg = '--revision={}'.format(p.get('revision'))
        else:
            rev_arg = ''

        password = p.get('password', '0000')

        self.adb_reboot_bootloader()

        cmd = ('ubuntu-device-flash --server={} {} touch --serial={} '
               '--channel={} --device={} --recovery-image=recovery.img '
               '--developer-mode --password={} '
               '--bootstrap'.format(server, rev_arg, self.config.get('serial'),
                                    p.get('channel'),
                                    self.config.get('device_type'), password))
        logger.info('Running ubuntu-device-flash')
        rc = runcmd(cmd)
        if rc:
            raise ProvisioningError("Flashing new image failed!")
        self.adb_wait_for_device()
        self.handle_welcome_wizard()
        self.handle_edges_intro()
        self.configure_network()

    def configure_network(self):
        netspec = self.config.get('network_spec')
        serial = self.config.get('serial')
        if not netspec:
            logger.warning('No network settings specified in the config')
            return
        logger.info('Configuring the network')
        rc = runcmd('phablet-config -s {} network --write "{}"'.format(
            serial, netspec))
        if rc:
            logger.error('Error configuring network')

    def handle_welcome_wizard(self):
        p = self.job_data.get('provision_data')
        wizard = p.get('welcome_wizard', 'off')
        if wizard.lower() == 'on':
            logger.info('Welcome wizard will be left enabled')
            return

        logger.info('Disabling the welcome wizard')
        serial = self.config.get('serial')
        cmd = ('phablet-config -s {} welcome-wizard '
               '--disable'.format(serial))
        rc = runcmd(cmd)
        if rc:
            raise ProvisioningError("Disable welcome wizard failed!")
        self.adb_wait_for_device()

    def handle_edges_intro(self):
        p = self.job_data.get('provision_data')
        intro = p.get('edges_intro', 'off')
        if intro.lower() == 'on':
            logger.info('Edges intro will be left enabled')
            return

        logger.info('Disabling the edges intro')
        serial = self.config.get('serial')
        cmd = ('phablet-config -s {} edges-intro '
               '--disable'.format(serial))
        rc = runcmd(cmd)
        if rc:
            raise ProvisioningError("Disable edges intro failed!")
        self.adb_wait_for_device()

    def adb_reboot_bootloader(self):
        serial = self.config.get('serial')
        cmd = 'adb -s {} reboot-bootloader'.format(serial)
        rc = runcmd(cmd)
        if rc:
            raise RecoveryError("Reboot to bootloader failed!")
            # FIXME: we should probably attempt hard-recovery here

    def adb_wait_for_device(self):
        serial = self.config.get('serial')
        cmd = 'adb -s {} wait-for-device'.format(serial)
        rc = runcmd(cmd)
        if rc:
            raise ProvisioningError("Wait for device failed!")

    def get_recovery_image(self):
        device = self.config.get('device_type')
        if not device:
            raise ProvisioningError('No device_type specified in config')
        url = ('http://people.canonical.com/~plars/touch/'
               'recovery-{}.img'.format(device))
        download(url, 'recovery.img')
