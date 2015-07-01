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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Beagle Bone Black support code."""

import os
import subprocess
import tempfile

import guacamole

from devices.bbb.beagleboneblack import BeagleBoneBlack
from . import constants

device_name = "bbb"


class provision(guacamole.Command):

    """Tool for provisioning beagle bone black with a given image."""

    def invoked(self, ctx):
        """Method called when the command is invoked."""
        device = BeagleBoneBlack()
        print("DEBUG: ensure_emmc_image")
        device.ensure_emmc_image()
        print("DEBUG: flash_sd")
        device.flash_sd(ctx.args.image_url)
        print("DEBUG: ensure_test_image")
        device.ensure_test_image()

    def register_arguments(self, parser):
        """Method called to customize the argument parser."""
        parser.add_argument('-i', '--image-url', required=True,
                            help='URL of the image to install')


class runtest(guacamole.Command):

    """Tool for running tests on a provisioned device."""

    def invoked(self, ctx):
        """Method called when the command is invoked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = os.path.split(ctx.args.test_url)[1]
            testdir = os.path.join(tmpdir, 'test')
            # XXX: Agent should pass us the output location
            outputdir = '/tmp/output'

            subprocess.check_output(['wget', ctx.args.test_url], cwd=tmpdir)
            os.makedirs(testdir)
            # Extraction directory does not get renamed, and test_cmd
            # gets run from one level above
            subprocess.check_output(['tar', '-xf', filename, '-C', testdir,
                                     '--strip-components=1'], cwd=tmpdir)
            test_cmd = ['adt-run', '--built-tree', testdir, '--output-dir',
                        outputdir, '---', 'ssh', '-d', '-l', 'ubuntu', '-P',
                        'ubuntu', '-H', constants.TEST_HOST]
            subprocess.check_output(test_cmd, cwd=tmpdir)

    def register_arguments(self, parser):
        """Method called to customize the argument parser."""
        parser.add_argument('-u', '--test-url', required=True,
                            help='URL of the test tarball')


class DeviceAgent(guacamole.Command):

    """Device agent for BeagleBone Black."""

    sub_commands = (
        ('provision', provision),
        ('runtest', runtest),
    )
