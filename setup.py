#!/usr/bin/env python
# Copyright (C) 2016-2022 Canonical
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
    "PyYAML",
    "requests",
    "voluptuous",
]

setup(
    name="testflinger-agent",
    version="1.0",
    long_description=__doc__,
    packages=["testflinger_agent"],
    zip_safe=False,
    install_requires=INSTALL_REQUIRES,
    setup_requires=["pytest-runner"],
    scripts=["testflinger-agent"],
)
