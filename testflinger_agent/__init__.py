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
import os
import sys
import time
import yaml

from testflinger_agent import (client, schema)

logger = logging.getLogger()

config = dict()


def main():
    args = parse_args()
    load_config(args.config)
    configure_logging()
    check_interval = config.get('polling_interval')
    while True:
        try:
            logger.info("Checking jobs")
            client.process_jobs()
            logger.info("Sleeping for {}".format(check_interval))
            time.sleep(check_interval)
        except KeyboardInterrupt:
            logger.info('Caught interrupt, exiting!')
            sys.exit(0)


def load_config(configfile):
    global config
    with open(configfile) as f:
        config = yaml.safe_load(f)
    config = schema.validate(config)


def configure_logging():
    global config
    os.makedirs(config.get('logging_basedir'), exist_ok=True)
    log_level = logging.getLevelName(config.get('logging_level'))
    # This should help if they specify something invalid
    if not isinstance(log_level, int):
        log_level = logging.INFO
    logfmt = logging.Formatter(
        fmt='[%(asctime)s] %(levelname)+7.7s: %(message)s',
        datefmt='%y-%m-%d %H:%M:%S')
    file_log = logging.FileHandler(
        filename=os.path.join(config.get('logging_basedir'),
                              'testflinger-agent.log'))
    file_log.setFormatter(logfmt)
    logger.addHandler(file_log)
    if not config.get('logging_quiet'):
        console_log = logging.StreamHandler()
        console_log.setFormatter(logfmt)
        logger.addHandler(console_log)
    logger.setLevel(log_level)


def parse_args():
    parser = argparse.ArgumentParser(description='Testflinger Agent')
    parser.add_argument('--config', '-c', default='testflinger-agent.conf',
                        help='Testflinger agent config file')
    return parser.parse_args()
