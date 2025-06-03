# Copyright (C) 2016-2023 Canonical
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
from collections import deque
from logging.handlers import TimedRotatingFileHandler
from threading import Timer
from urllib.parse import urljoin

import requests
import yaml
from requests.adapters import HTTPAdapter, Retry
from urllib3.exceptions import HTTPError

from testflinger_agent import schema
from testflinger_agent.agent import TestflingerAgent
from testflinger_agent.client import TestflingerClient

logger = logging.getLogger(__name__)


class ReqBufferTimer(Timer):
    """Requests buffer flush."""

    def run(self):
        """Loop timer."""
        while not self.finished.wait(self.interval):
            self.function(*self.args, **self.kwargs)


class ReqBufferHandler(logging.Handler):
    """Requests logging handler."""

    def __init__(self, agent, server):
        super().__init__()
        if not server.lower().startswith("http"):
            server = "http://" + server
        uri = urljoin(server, "/v1/agents/data/")
        self.url = urljoin(uri, agent)
        self.qdepth = 100  # messages
        self.reqbuffer = deque([], maxlen=self.qdepth)
        self.reqbuff_timer = None
        self.reqbuff_interval = 10.0  # seconds
        self._start_reqbuff_timer()
        # reuse socket
        self.session = self._requests_retry()

    def _requests_retry(self, retries=3):
        """Retry api server."""
        session = requests.Session()
        retry = Retry(
            total=retries,
            read=retries,
            connect=retries,
            backoff_factor=0.3,
            status_forcelist=(500, 502, 503, 504),
            allowed_methods=False,  # allow retry on all methods
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _start_reqbuff_timer(self):
        """Periodically check and send buffer."""
        self.reqbuff_timer = ReqBufferTimer(self.reqbuff_interval, self.flush)
        # terminate timer on exit
        self.reqbuff_timer.daemon = True
        self.reqbuff_timer.start()

    def emit(self, record):
        """Write logging events to buffer."""
        if len(self.reqbuffer) >= self.qdepth:
            self.reqbuffer.popleft()

        self.reqbuffer.append(record)

    def flush(self):
        """Flush and post buffer."""
        # list conversion for atomic iteration
        records = [record.getMessage() for record in list(self.reqbuffer)]

        try:
            self.session.post(
                url=self.url, json=self.format(records), timeout=5
            )
        except (requests.RequestException, HTTPError) as error:
            logger.debug(error)

            return  # preserve buffer

        self.reqbuffer.clear()

    def close(self):
        """Cleanup on handler close."""
        self.reqbuff_timer.cancel()


class ReqBufferFormatter(logging.Formatter):
    """Format logging messages."""

    def format(self, records):
        return {"log": records}


def start_agent():
    args = parse_args()
    config = load_config(args.config)
    config["metrics_endpoint_port"] = args.metrics_port
    configure_logging(config)
    check_interval = config.get("polling_interval")
    client = TestflingerClient(config)
    agent = TestflingerAgent(client)
    while True:
        offline_file = agent.check_offline()
        if offline_file:
            logger.error(
                "Agent %s is offline, not processing jobs! "
                "Remove %s to resume processing",
                config.get("agent_id"),
                offline_file,
            )
            while agent.check_offline():
                time.sleep(check_interval)
        # Refresh the updated_at timestamp on advertised queues
        client.post_advertised_queues()
        logger.info("Checking jobs")
        agent.process_jobs()
        logger.info("Sleeping for %d", check_interval)
        time.sleep(check_interval)


def load_config(configfile):
    with open(configfile) as f:
        config = yaml.safe_load(f)
    config = schema.validate(config)
    return config


def configure_logging(config):
    # Create these at the beginning so we fail early if there are
    # permission problems
    os.makedirs(config.get("logging_basedir"), exist_ok=True)
    os.makedirs(config.get("results_basedir"), exist_ok=True)
    log_level = logging.getLevelName(config.get("logging_level"))
    # This should help if they specify something invalid
    if not isinstance(log_level, int):
        log_level = logging.INFO
    logfmt = logging.Formatter(
        fmt=(
            "[%(asctime)s] %(levelname)+7.7s: "
            "(%(filename)s:%(lineno)d)| %(message)s"
        ),
        datefmt="%y-%m-%d %H:%M:%S",
    )
    log_path = os.path.join(
        config.get("logging_basedir"), "testflinger-agent.log"
    )
    file_log = TimedRotatingFileHandler(
        log_path, when="midnight", interval=1, backupCount=6
    )
    file_log.setFormatter(logfmt)
    logger.addHandler(file_log)
    # requests logging
    # inherit from logger __name__
    """ DEBUG: Temporarily disable sending agent logs to the server
    req_logger = logging.getLogger()
    request_formatter = ReqBufferFormatter()
    request_handler = ReqBufferHandler(
        config.get("agent_id"), config.get("server_address")
    )
    request_handler.setFormatter(request_formatter)
    req_logger.addHandler(request_handler)
    req_logger.setLevel(log_level)
    """
    if not config.get("logging_quiet"):
        console_log = logging.StreamHandler()
        console_log.setFormatter(logfmt)
        logger.addHandler(console_log)
    logger.setLevel(log_level)


def parse_args():
    parser = argparse.ArgumentParser(description="Testflinger Agent")
    parser.add_argument(
        "--config",
        "-c",
        default="testflinger-agent.conf",
        help="Testflinger agent config file",
    )
    parser.add_argument(
        "--metrics_port",
        "-p",
        default="8000",
        type=int,
        help="Port to expose metrics endpoint on",
    )
    return parser.parse_args()
