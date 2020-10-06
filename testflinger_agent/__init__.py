# Copyright (C) 2016-2017 Canonical
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
import time
import yaml

from testflinger_agent import schema
from testflinger_agent.agent import TestflingerAgent
from testflinger_agent.client import TestflingerClient
from logging.handlers import TimedRotatingFileHandler

logger = logging.getLogger(__name__)


def main():
    args = parse_args()
    config = load_config(args.config)
    configure_logging(config)
    check_interval = config.get('polling_interval')
    client = TestflingerClient(config)
    agent = TestflingerAgent(client)
    while True:
        offline_file = agent.check_offline()
        if offline_file:
            logger.error("Agent %s is offline, not processing jobs! "
                         "Remove %s to resume processing" %
                         (config.get('agent_id'), offline_file))
            while agent.check_offline():
                time.sleep(check_interval)
        logger.info("Checking jobs")
        agent.process_jobs()
        logger.info("Sleeping for {}".format(check_interval))
        time.sleep(check_interval)


def load_config(configfile):
    with open(configfile) as f:
        config = yaml.safe_load(f)
    config = schema.validate(config)
    return config


def configure_logging(config):
    # Create these at the beginning so we fail early if there are
    # permission problems
    os.makedirs(config.get('logging_basedir'), exist_ok=True)
    os.makedirs(config.get('results_basedir'), exist_ok=True)
    log_level = logging.getLevelName(config.get('logging_level'))
    # This should help if they specify something invalid
    if not isinstance(log_level, int):
        log_level = logging.INFO
    logfmt = logging.Formatter(
        fmt='[%(asctime)s] %(levelname)+7.7s: %(message)s',
        datefmt='%y-%m-%d %H:%M:%S')
    log_path = os.path.join(
        config.get('logging_basedir'), 'testflinger-agent.log')
    file_log = TimedRotatingFileHandler(log_path,
                                        when="midnight",
                                        interval=1,
                                        backupCount=6)
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
