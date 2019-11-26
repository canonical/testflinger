#!/usr/bin/env python3
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

import os
import sys

from setuptools import (
    find_packages,
    setup,
)
assert sys.version_info >= (3,), 'Python 3 is required'


VERSION = '0.0.1'

datafiles = [(d, [os.path.join(d, f) for f in files])
             for d, folders, files in os.walk('data')]

TEST_REQUIRES = [
    "pytest",
]

setup(
    name='snappy-device-agents',
    version=VERSION,
    description=('Device agents scripts for provisioning and running '
                 'tests on Snappy devices'),
    author='Snappy Device Agents Developers',
    author_email='paul.larson@canonical.com',
    url='https://launchpad.net/snappy-device-agents',
    license='GPLv3',
    packages=find_packages(),
    data_files=datafiles,
    setup_requires=['pytest-runner'],
    install_requires=['PyYAML>=3.11',
                      'netifaces>=0.10.4'],
    tests_require=TEST_REQUIRES,
    scripts=['snappy-device-agent'],
)
