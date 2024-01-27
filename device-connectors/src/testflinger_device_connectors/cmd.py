#!/usr/bin/env python
# Copyright (C) 2023-2024 Canonical
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
Main testflinger-device-connectors command module
"""


import argparse
import logging
import sys

from testflinger_device_connectors.devices import (
    DEVICE_CONNECTORS,
    get_device_stage_func,
)

logger = logging.getLogger()


STAGES = (
    "provision",
    "firmware_update",
    "runtest",
    "allocate",
    "reserve",
    "cleanup",
)


def get_args(argv=None):
    """main command function for testflinger-device-connectors"""
    parser = argparse.ArgumentParser()

    # First add a subcommand for each supported device type
    dev_parser = parser.add_subparsers(dest="device", required=True)
    for dev_name in DEVICE_CONNECTORS:
        dev_subparser = dev_parser.add_parser(dev_name)

        # Next add the subcommands that can be used
        cmd_subparser = dev_subparser.add_subparsers(
            dest="stage", required=True
        )

        for stage in STAGES:
            cmd_parser = cmd_subparser.add_parser(stage)
            cmd_parser.add_argument(
                "-c",
                "--config",
                required=True,
                help="Config file for this device",
            )
            cmd_parser.add_argument(
                "job_data", help="Testflinger json data file"
            )

    return parser.parse_args(argv)


def main():
    """
    Dynamically load the selected module and call the selected method
    """
    args = get_args()
    func = get_device_stage_func(args.device, args.stage)
    sys.exit(func(args))
