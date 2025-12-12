#!/usr/bin/env python3
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
Generate sample data for use in local testing and development.
This will send the data to the Testflinger server specified, but will not
allow you to use the production server.
"""

import logging
import random
import sys
from argparse import ArgumentParser, Namespace
from datetime import datetime, timezone
from typing import Iterator, Optional, Tuple

import requests

logging.basicConfig(level=logging.INFO)


def get_args() -> Namespace:
    """Parse command line arguments
    :return: Namespace containing parsed arguments
    """
    default_testflinger_server = "http://localhost:5000"
    parser = ArgumentParser(
        description="Create sample data for testing Testflinger"
    )

    def _server_validator(server: str) -> str:
        if not server.startswith("http"):
            raise ValueError("Server must start with http")
        if "testflinger.canonical.com" in server:
            raise ValueError("Cannot use production server")
        return server

    parser.add_argument(
        "-a",
        "--agents",
        type=int,
        default=10,
        help="Number of agents to create",
    )

    parser.add_argument(
        "-j", "--jobs", type=int, default=10, help="Number of jobs to create"
    )

    parser.add_argument(
        "-q",
        "--queues",
        type=int,
        default=10,
        help="Number of queues to create",
    )

    parser.add_argument(
        "-s",
        "--server",
        default=default_testflinger_server,
        type=_server_validator,
        help=(
            "URL of testflinger server starting with 'http(s)://...' "
            "(must not be production server)"
        ),
    )
    return parser.parse_args()


class AgentDataGenerator:  # pylint: disable=too-few-public-methods
    """Agent data generator"""

    def __init__(
        self,
        prefix: str = "agent",
        num_agents: int = 10,
        queue_list: Optional[Tuple[str, ...]] = None,
    ):
        """Generate sample agent data
        :param prefix: Prefix for the agent name
        :param num_agents: Number of agents to generate
        :param queue_list: Tuple of queues to assign to agents
        :return: List of dictionaries containing agent data
        self.data_list = []
        for agent_num in range(num_agents):
            agent_data: dict = {
                "state": random.choice(("waiting", "test", "provision")),
            }
            if queue_list:
                agent_data["queues"] = [random.choice(queue_list)]
            self.data_list.append({f"{prefix}{agent_num}": agent_data})
        """
        self.prefix = prefix
        self.num_agents = num_agents
        self.queue_list = queue_list

    def __iter__(self):
        for agent_num in range(self.num_agents):
            agent_data = {
                "state": random.choice(("waiting", "test", "provision")),
            }
            if self.queue_list:
                agent_data["queues"] = random.sample(self.queue_list, random.randint(1, len(self.queue_list)))
            yield (f"{self.prefix}{agent_num}", agent_data)


class JobDataGenerator:  # pylint: disable=too-few-public-methods
    """Job data generator"""

    def __init__(
        self,
        prefix: str = "job",
        num_jobs: int = 10,
        queue_list: Optional[Tuple[str, ...]] = None,
    ):
        """Generate sample job data
        :param prefix: Prefix for the job name
        :param num_jobs: Number of jobs to generate
        :param queue_list: Tuple of queues to assign to jobs
        :return: List of dictionaries containing job data
        """
        self.prefix = prefix
        self.num_jobs = num_jobs
        self.queue_list = queue_list

    def __iter__(self):
        for _ in range(self.num_jobs):
            yield {
                "job_queue": random.choice(self.queue_list),
                "test_data": {"test_cmds": "echo test"},
            }


class QueueDataGenerator:  # pylint: disable=too-few-public-methods
    """Queue data generator"""

    def __init__(
        self,
        prefix: str = "test_queue",
        description: str = "Example queue",
        num_queues: int = 10,
    ):
        """Generate sample queue data
        :param prefix: Prefix for the queue name
        :param description: Description for the queue
        :param num_queues: Number of queues to generate
        :return: List of dictionaries containing queue data
        """
        self.prefix = prefix
        self.description = description
        self.num_queues = num_queues

    def __iter__(self):
        for queue_num in range(self.num_queues):
            yield {
                f"{self.prefix}{queue_num}": f"{self.description} {queue_num}"
            }


class TestflingerClient:
    """Client to connect to Testflinger and post data"""

    def __init__(self, server_url: str):
        self.server_url = server_url
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.session.timeout = 3

    def post_queue_data(self, queues: Iterator):
        """Post queue data to Testflinger server
        :param queues: Iterator of queue data to post
        """
        for queue in queues:
            self.session.post(
                f"{self.server_url}/v1/agents/queues",
                json=queue,
            )

    def post_agent_data(self, agents: Iterator):
        """Post agent data to Testflinger server
        :param agents: Iterator of agent data to post
        """
        for agent_name, agent_data in agents:
            self.session.post(
                f"{self.server_url}/v1/agents/data/{agent_name}",
                json=agent_data,
            )

            # Add failed provision logs with obviously fake job_id for testing
            exit_code = random.choice((0, 1))
            exit_detail = (
                "provision_fail" if exit_code != 0 else "provision_pass"
            )
            provision_log = {
                "job_id": "00000000-0000-0000-0000-00000000000",
                "exit_code": exit_code,
                "detail": exit_detail,
            }
            self.session.post(
                f"{self.server_url}/v1/agents/provision_logs/{agent_name}",
                json=provision_log,
            )

    def post_job_data(self, jobs: Iterator):
        """Post job data to Testflinger server
        :param jobs: Iterator of job data to post
        """
        for job in jobs:
            self.session.post(
                f"{self.server_url}/v1/job",
                json=job,
            )


def extract_queue_names(queues: Iterator) -> Tuple[str, ...]:
    """Extract queue names from queue data
    :param queues: Iterator of queue data
    :return: Tuple of queue names
    """
    return tuple(
        queue_name for queue_entry in queues for queue_name in queue_entry
    )


def main():
    """Main function"""
    args = get_args()

    testflinger_client = TestflingerClient(server_url=args.server)

    queues = QueueDataGenerator(num_queues=args.queues)
    testflinger_client.post_queue_data(queues=queues)
    logging.info("Created %s queues", args.queues)

    valid_queue_names = extract_queue_names(queues=queues)

    agents = AgentDataGenerator(
        num_agents=args.agents, queue_list=valid_queue_names
    )
    testflinger_client.post_agent_data(agents=agents)
    logging.info("Created %s agents", args.agents)

    jobs = JobDataGenerator(num_jobs=args.jobs, queue_list=valid_queue_names)
    testflinger_client.post_job_data(jobs=jobs)
    logging.info("Created %s jobs", args.jobs)


if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.RequestException as error:
        logging.error(error)
        sys.exit(1)
