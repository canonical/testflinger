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
"""Main testflinger-device-connectors command module."""

import argparse
import json
import logging
import sys
from typing import Callable

import yaml

from testflinger_device_connectors import configure_logging, write_device_info
from testflinger_device_connectors.devices import (
    DEVICE_CONNECTORS,
    RecoveryError,
    get_device_stage_func,
)

logger = logging.getLogger(__name__)


STAGES = (
    "provision",
    "firmware_update",
    "runtest",
    "allocate",
    "reserve",
    "cleanup",
)


def get_args(argv=None):
    """Command function for testflinger-device-connectors."""
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


def add_exception_logging_to_file(func: Callable, stage: str):
    """Add logging of exceptions to a json file,
    used as a decorator function.
    """

    def _wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as exception:
            logger.error(exception)
            if exception.__cause__ is None:
                exception_cause = None
            else:
                exception_cause = repr(exception.__cause__)
            exception_info = {
                f"{stage}_exception_info": {
                    "exception_name": type(exception).__name__,
                    "exception_message": str(exception),
                    "exception_cause": exception_cause,
                }
            }
            with open(
                "device-connector-error.json", "a", encoding="utf-8"
            ) as error_file:
                error_file.write(json.dumps(exception_info))
            if isinstance(exception, RecoveryError):
                return 46
            else:
                return 1

    return _wrapper


def main():
    """Dynamically load the selected module and call the selected method."""
    args = get_args()
    with open(args.config) as configfile:
        config = yaml.safe_load(configfile)
    configure_logging(config)
    write_device_info(config)

    func = add_exception_logging_to_file(
        get_device_stage_func(args.device, args.stage), args.stage
    )
    sys.exit(func(args))
