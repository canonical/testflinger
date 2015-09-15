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
from guacamole.core import Ingredient
from guacamole.recipes.cmd import CommandRecipe
from guacamole.ingredients import ansi
from guacamole.ingredients import argparse
from guacamole.ingredients import cmdtree

from devices import load_devices

logger = logging.getLogger()


class CrashLoggingIngredient(Ingredient):
    """Use python logging if we Crash
    """

    def dispatch_failed(self, context):
        logger.exception("exception")
        raise


class AgentCommandRecipe(CommandRecipe):
    """This is so we can add a custom ingredient
    """

    def get_ingredients(self):
        return [
            cmdtree.CommandTreeBuilder(self.command),
            cmdtree.CommandTreeDispatcher(),
            argparse.AutocompleteIngredient(),
            argparse.ParserIngredient(),
            ansi.ANSIIngredient(),
            CrashLoggingIngredient(),
        ]


class Agent(Command):
    """Main agent command

    This loads subcommands from modules in the devices directory
    """

    sub_commands = load_devices()

    # XXX: Remove for now due to https://github.com/zyga/guacamole/issues/4
    """
    def invoked(self, ctx):
        print(ctx.parser.format_help())
        exit(1)
    """

    def main(self, argv=None, exit=True):
        return AgentCommandRecipe(self).main(argv, exit)


def main():
    Agent().main()
