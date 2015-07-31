#!/usr/bin/env python
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


import logging

from guacamole import Command

from devices import load_devices


class Agent(Command):
    """Main agent command

    This loads subcommands from modules in the devices directory
    """
    spices = ['log:arguments']

    sub_commands = load_devices()

    # XXX: Remove for now due to https://github.com/zyga/guacamole/issues/4
    """
    def invoked(self, ctx):
        print(ctx.parser.format_help())
        exit(1)
    """


def main():
    logging.basicConfig(level=logging.INFO)
    Agent().main()
