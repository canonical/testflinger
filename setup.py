#!/usr/bin/env python3
# Copyright (C) 2016 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#


from setuptools import setup

INSTALL_REQUIRES = [
    "gunicorn",
    "redis",
    "flask",
]

TEST_REQUIRES = [
    "fakeredis",
    "mock",
    "pytest",
    "pytest-cov",
    "pytest-mock",
    "pytest-flake8",
]

setup(
    name='testflinger',
    version='1.0.1',
    long_description=__doc__,
    packages=['testflinger'],
    zip_safe=False,
    install_requires=INSTALL_REQUIRES,
    setup_requires=['pytest-runner'],
    tests_require=TEST_REQUIRES,
)
