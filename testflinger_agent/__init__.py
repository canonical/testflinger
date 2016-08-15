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

import argparse
import logging
import yaml

from testflinger_agent import schema

logger = logging.getLogger()

config = dict()


def main():
    args = parse_args()
    load_config(args.config)


def load_config(configfile):
    global config
    with open(configfile) as f:
        config = yaml.safe_load(f)
    config = schema.validate(config)


def parse_args():
    parser = argparse.ArgumentParser(description='Testflinger Agent')
    parser.add_argument('--config', '-c', default='testflinger-agent.conf',
                        help='Testflinger agent config file')
    return parser.parse_args()
