#!/usr/bin/env python
# Copyright (C) 2023 Canonical
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
"""
Main snappy-device-agents command module
"""


import argparse
import logging

from snappy_device_agents.devices import load_devices

logger = logging.getLogger()


def main():
    """main command function for snappy-device-agents"""
    devices = load_devices()
    parser = argparse.ArgumentParser()

    # First add a subcommand for each supported device type
    dev_parser = parser.add_subparsers()
    for dev_name, dev_class in devices:
        dev_subparser = dev_parser.add_parser(dev_name)
        dev_module = dev_class()
        # Next add the subcommands that can be used and the methods they run
        cmd_subparser = dev_subparser.add_subparsers()
        for cmd, func in (
            ("provision", dev_module.provision),
            ("runtest", dev_module.runtest),
            ("allocate", dev_module.allocate),
            ("reserve", dev_module.reserve),
        ):
            cmd_parser = cmd_subparser.add_parser(cmd)
            cmd_parser.add_argument(
                "-c",
                "--config",
                required=True,
                help="Config file for this device",
            )
            cmd_parser.add_argument(
                "job_data", help="Testflinger json data file"
            )
            cmd_parser.set_defaults(func=func)
    args = parser.parse_args()
    raise SystemExit(args.func(args))
