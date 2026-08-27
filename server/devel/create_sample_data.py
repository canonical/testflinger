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
import os
import random
import sys
from argparse import ArgumentParser, Namespace
from collections import defaultdict
from datetime import datetime, timezone
from typing import Iterator, Optional, Tuple

import requests
from sample_users import SAMPLE_CLIENTS

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
        help="Number of queues to distribute amongst jobs and agents",
    )

    parser.add_argument(
        "-d",
        "--advertised-queues",
        type=int,
        default=1,
        help="Number of advertised queues to create",
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
                "state": "waiting",
            }
            if self.queue_list:
                agent_data["queues"] = random.sample(
                    self.queue_list, random.randint(1, min(3, len(self.queue_list)))
                )
            yield (f"{self.prefix}{agent_num}", agent_data)


SAMPLE_PROVISION_DATA = (
    {"url": "http://cdimage.example/ubuntu-22.04-arm64.img.xz"},
    {"url": "http://cdimage.example/ubuntu-24.04-amd64.img.xz"},
    {"distro": "jammy"},
)


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
                "provision_data": random.choice(SAMPLE_PROVISION_DATA),
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

    def __init__(
        self,
        server_url: str,
        client_id: Optional[str] = None,
        client_key: Optional[str] = None,
    ):
        self.server_url = server_url
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.session.timeout = 3
        if client_id and client_key:
            self._authenticate(client_id, client_key)

    def _authenticate(self, client_id: str, client_key: str) -> None:
        """Fetch a Bearer token and attach it to the session.
        :param client_id: Client ID for authentication
        :param client_key: Client key/secret for authentication
        """
        response = self.session.post(
            f"{self.server_url}/v1/oauth2/token",
            auth=(client_id, client_key),
        )
        response.raise_for_status()
        token = response.json()["access_token"]
        self.session.headers.update({"Authorization": f"Bearer {token}"})

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

    def assign_job_to_agent(self, agent_name: str, job_id: str) -> None:
        """Record a running job on an agent, setting an active state.

        Sets both job_id and a random active state so the agent record is
        consistent with actually executing a job.

        :param agent_name: Name of the agent
        :param job_id: UUID of the job to associate
        """
        active_state = random.choice(
            ("setup", "provision", "test", "allocate", "reserve")
        )
        self.session.post(
            f"{self.server_url}/v1/agents/data/{agent_name}",
            json={"job_id": job_id, "state": active_state},
        )

    def post_job_results(
        self, job_id: str, agent_name: str, job_state: str
    ) -> None:
        """Post result data for a job, recording agent and final state.
        :param job_id: UUID of the job
        :param agent_name: Name of the agent that ran the job
        :param job_state: Final state for the job (e.g. 'complete', 'running')
        """
        self.session.post(
            f"{self.server_url}/v1/result/{job_id}",
            json={"agent_id": agent_name, "job_state": job_state},
        )

    def post_job_data(self, jobs: Iterator) -> list:
        """Post job data to Testflinger server
        :param jobs: Iterator of job data to post
        :return: List of (job_id, queue) tuples for successfully created jobs
        """
        results = []
        for job in jobs:
            response = self.session.post(
                f"{self.server_url}/v1/job",
                json=job,
            )
            if response.ok:
                job_id = response.json().get("job_id")
                if job_id:
                    results.append((job_id, job["job_queue"]))
        return results


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

    # Primary client used for queue/agent setup (needs admin role)
    admin_client = TestflingerClient(
        server_url=args.server,
        client_id=os.environ.get("TESTFLINGER_CLIENT_ID", "testflinger-admin"),
        client_key=os.environ.get("TESTFLINGER_SECRET_KEY", "testflinger"),
    )

    queues = QueueDataGenerator(num_queues=args.queues)
    # configure "advertised" queues:
    admin_client.post_queue_data(
        random.sample(tuple(queues), random.randint(1, args.advertised_queues))
    )
    logging.info("Created %s queues", args.queues)

    valid_queue_names = extract_queue_names(queues=queues)

    agents = AgentDataGenerator(
        num_agents=args.agents, queue_list=valid_queue_names
    )
    agent_list = list(agents)
    admin_client.post_agent_data(iter(agent_list))
    logging.info("Created %s agents", args.agents)

    # Only post jobs to queues that at least one agent actually serves —
    # otherwise waiting jobs would sit forever with no agent able to pick them up.
    served_queues = tuple(
        queue
        for _, agent_data in agent_list
        for queue in agent_data.get("queues", [])
    )
    if not served_queues:
        logging.error("No agents have queues assigned; cannot post jobs")
        return

    # Post jobs distributed across all known dev client IDs so that each
    # job is stamped with a realistic client_id by the server.  The client
    # IDs here must match the credential-based accounts created by
    # create_sample_users.py (from the SAMPLE_CLIENTS list).
    job_client_ids = [
        sample["client_id"]
        for sample
        in SAMPLE_CLIENTS
    ]
    job_clients = [
        TestflingerClient(
            server_url=args.server,
            client_id=client_id,
            client_key="testflinger",
        )
        for client_id in job_client_ids
    ]

    jobs = JobDataGenerator(num_jobs=args.jobs, queue_list=served_queues)
    # Collect (job_id, queue) so we can match agents by their queues
    job_results = []
    for job in jobs:
        job_results.extend(random.choice(job_clients).post_job_data([job]))
    logging.info("Created %s jobs", args.jobs)

    # Build a queue → [agent_names] map covering ALL agents regardless of
    # state, since completed/cancelled jobs can have run on any agent.
    queue_to_agents: dict = defaultdict(list)
    for agent_name, agent_data in agent_list:
        for queue in agent_data.get("queues", []):
            queue_to_agents[queue].append(agent_name)

    # Track which agents currently have a running job so we don't assign two.
    agent_running_job: dict = {}

    # Job states with realistic weights:
    #   most jobs are complete, a handful are running or still waiting
    job_states = ("complete", "running", "waiting", "cancelled")
    job_state_weights = (60, 15, 20, 5)

    associations = 0
    for job_id, queue in job_results:
        job_state = random.choices(job_states, weights=job_state_weights)[0]

        if job_state == "waiting":
            # Still queued — no agent assigned yet
            continue

        # Pick a random agent that serves this queue
        candidates = queue_to_agents.get(queue, [])
        if not candidates:
            continue

        if job_state == "running":
            # Only assign to agents not already running a job; skip this job
            # if every candidate is occupied (one active job per agent, always)
            free = [a for a in candidates if a not in agent_running_job]
            if not free:
                continue
            agent_name = random.choice(free)
            admin_client.assign_job_to_agent(agent_name, job_id)
            agent_running_job[agent_name] = job_id
        else:
            agent_name = random.choice(candidates)

        admin_client.post_job_results(job_id, agent_name, job_state)
        associations += 1

    logging.info("Associated %s jobs with agents", associations)


if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.RequestException as error:
        logging.error(error)
        sys.exit(1)
