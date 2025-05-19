# Copyright (C) 2025 Canonical Ltd.
"""Testflinger client module."""

import base64
import logging
import urllib.parse
from functools import cached_property
from http import HTTPStatus
from pathlib import Path
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class Client:
    """Testflinger client."""

    def __init__(
        self,
        server: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        retries: int = 3,
    ) -> None:
        self.server = server
        self.client_id = client_id
        self.client_secret = client_secret
        self.retries = retries

    @cached_property
    def session(self) -> requests.Session:
        """Create a requests session with retry logic."""
        session = requests.Session()
        retry = Retry(
            total=self.retries,
            read=self.retries,
            connect=self.retries,
            backoff_factor=0.3,
            status_forcelist=(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                HTTPStatus.BAD_GATEWAY,
                HTTPStatus.SERVICE_UNAVAILABLE,
                HTTPStatus.GATEWAY_TIMEOUT,
            ),
            allowed_methods=None,  # allow retry on all methods
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    @cached_property
    def token(self) -> str:
        """Return the token for the client."""
        if not self.client_id or not self.client_secret:
            return ""
        url = urllib.parse.urljoin(self.server, "/v1/oauth2/token")
        id_key_pair = f"{self.client_id}:{self.client_secret}"
        encoded_id_key_pair = base64.b64encode(id_key_pair.encode()).decode()
        headers = {"Authorization": f"Basic {encoded_id_key_pair}"}
        response = self.session.post(url, headers=headers)
        response.raise_for_status()
        return response.text

    @cached_property
    def auth_headers(self) -> Optional[dict]:
        """Create an authorization header for the client."""
        if not self.token:
            return None
        return {"Authorization": f"{self.token}"}

    def submit_job(self, job_data: dict) -> str:
        """Submit a test job to the server."""
        url = urllib.parse.urljoin(self.server, "/v1/job")
        headers = self.auth_headers
        response = self.session.post(url, json=job_data, headers=headers)
        response.raise_for_status()
        return response.json().get("job_id")

    def cancel_job(self, job_id: str) -> None:
        """Cancel a test job on the server."""
        self.post_job_action(job_id=job_id, action="cancel")

    def submit_job_attachment(
        self, job_id: str, path: Path, timeout_sec: float = 30
    ) -> None:
        """Submit a test job's attachment to the server."""
        endpoint = f"/v1/job/{job_id}/attachments"
        self.post_file(endpoint=endpoint, path=path, timeout_sec=timeout_sec)

    def get_job_attachments(
        self, job_id: str, path: Path, timeout_sec: float = 600
    ) -> None:
        """Get the attachments of a test job."""
        endpoint = f"/v1/job/{job_id}/attachments"
        self.get_file(endpoint=endpoint, path=path, timeout_sec=timeout_sec)

    def post_job_results(self, job_id: str, data: dict) -> None:
        """Post the results of a test job."""
        url = urllib.parse.urljoin(self.server, f"/v1/result/{job_id}")
        response = self.session.post(url, json=data, timeout=30)
        response.raise_for_status()

    def get_job_results(self, job_id: str) -> dict:
        """Get the results of a test job."""
        url = urllib.parse.urljoin(self.server, f"/v1/result/{job_id}")
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_job_artifacts(self, job_id: str, path: Path) -> None:
        """Get the artifacts of a test job."""
        endpoint = f"/v1/result/{job_id}/artifact"
        self.get_file(endpoint=endpoint, path=path)

    def post_job_artifacts(self, job_id: str, path: Path) -> None:
        """Post the artifacts of a test job."""
        endpoint = f"/v1/result/{job_id}/artifact"
        self.post_file(endpoint=endpoint, path=path)

    def get_jobs(self, queues: list[str]) -> dict:
        """Get the list of jobs from the server.

        :param queues: List of queues to filter jobs by.
        """
        url = urllib.parse.urljoin(self.server, "/v1/job")
        params = {"queue": queues}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_job(self, job_id: str) -> dict:
        """Get the job definition for a specified ID."""
        url = urllib.parse.urljoin(self.server, f"/v1/job/{job_id}")
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_job_status(self, job_id: str) -> str:
        """Get the status of a test job."""
        results = self.get_job_results(job_id)
        return results.get("job_state", "unknown")

    def get_job_position(self, job_id: str) -> int:
        """Get the position of a test job in the queue."""
        url = urllib.parse.urljoin(self.server, f"/v1/job/{job_id}/position")
        response = self.session.get(url)
        response.raise_for_status()
        return int(response.text)

    def post_job_provision_log(
        self, agent_id: str, job_id: str, exit_code: int, detail: str
    ) -> None:
        """Post the outcome of a test job's provision phase."""
        data = {
            "job_id": job_id,
            "exit_code": exit_code,
            "detail": detail,
        }
        url = urllib.parse.urljoin(
            self.server, f"/v1/agents/provision_logs/{job_id}/{agent_id}"
        )
        response = self.session.post(url, json=data, timeout=30)
        response.raise_for_status()

    def post_job_status_update(
        self,
        job_queue: str,
        agent_id: str,
        webhook: str,
        job_id: str,
        events: list[dict[str, str]],
    ) -> None:
        """Post a status update of a test job.

        :param job_queue: The queue the job is in.
        :param agent_id: The ID of the agent.
        :param webhook: The webhook URL to send the status update to.
        :param job_id: The ID of the job.
        :param events: List of accumulated events.
        """
        if not webhook:
            return
        url = urllib.parse.urljoin(self.server, f"/v1/job/{job_id}/events")
        data = {
            "agent_id": agent_id,
            "job_queue": job_queue,
            "job_status_webhook": webhook,
            "events": events,
        }
        response = self.session.post(url, json=data, timeout_sec=30)
        response.raise_for_status()

    def post_job_output(self, job_id: str, output: str) -> None:
        """Post the output of a test job."""
        url = urllib.parse.urljoin(self.server, f"/v1/job/{job_id}/output")
        data = {"output": output}
        response = self.session.post(url, json=data, timeout_sec=60)
        response.raise_for_status()

    def get_job_output(self, job_id: str) -> str:
        """Get the latest output for a test job."""
        url = urllib.parse.urljoin(self.server, f"/v1/job/{job_id}/output")
        response = self.session.get(url)
        response.raise_for_status()
        return response.text

    def get_job_serial_output(self, job_id: str) -> str:
        """Get the latest serial output for a test job."""
        url = urllib.parse.urljoin(self.server, f"/v1/job/{job_id}/serial_output")
        response = self.session.get(url)
        response.raise_for_status()
        return response.text

    def post_queues(self, queues: dict[str, str]) -> None:
        """Post the advertised queues to the server.

        :param queues: Dictionary of queue name to queue description.
        """
        url = urllib.parse.urljoin(self.server, "/v1/agents/queues")
        response = self.session.post(url, json=queues, timeout=30)
        response.raise_for_status()

    def get_queues(self) -> dict:
        """Get the advertised queues from the server."""
        url = urllib.parse.urljoin(self.server, "/v1/agents/queues")
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def post_queue_images(
        self, images: dict[str, list[dict[str, str]]]
    ) -> None:
        """Post the advertised images for a queue to the server.

        :param images: Dictionary of queue name to list of mapping of image name
            to field in provision data. For example:

            ```
                {
                    "queue_name": [
                        {
                            "latest": "url: http://path/to/latest.img.xz",
                            "stable": "url: http://path/to/stable.img.xz",
                        }
                    ]
                }
            ```
        """
        url = urllib.parse.urljoin(self.server, "/v1/agents/images")
        response = self.session.post(url, json=images)
        response.raise_for_status()

    def get_queue_images(self, queue: str) -> dict:
        """Get the advertised images for a queue from the server."""
        url = urllib.parse.urljoin(self.server, f"/v1/agents/images/{queue}")
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_queue_agents(self, queue: str) -> dict:
        """Get the list of all agents listening to a specified queue."""
        url = urllib.parse.urljoin(self.server, f"/v1/queues/{queue}/agents")
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_queue_wait_times(self, queues: Optional[list[str]] = None) -> dict:
        """Get the wait times for a list of queues."""
        queues = queues or []
        url = urllib.parse.urljoin(self.server, "/v1/queues/wait_times")
        params = {"queue": queues}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def post_agent_data(self, agent_id: str, data: dict) -> None:
        """Post the agent data to the server.

        :param agent_id: The ID of the agent.
        :param data: The data to post.
        """
        url = urllib.parse.urljoin(self.server, f"/v1/agents/data/{agent_id}")
        response = self.session.post(url, json=data, timeout=30)
        response.raise_for_status()

    def post_job_action(self, job_id: str, action: str) -> None:
        """Post an action to a test job."""
        url = urllib.parse.urljoin(self.server, f"/v1/job/{job_id}/action")
        data = {"action": action}
        response = self.session.post(url, json=data)
        response.raise_for_status()

    def get_file(
        self,
        endpoint: str,
        path: Path,
        timeout_sec: float = 30,
        chunk_size: int = 4096,
    ) -> None:
        """Get a file from the server."""
        uri = urllib.parse.urljoin(self.server, endpoint)
        response = requests.get(uri, timeout=timeout_sec, stream=True)
        response.raise_for_status()
        with path.open("wb") as file:
            for chunk in response.iter_content(chunk_size=chunk_size):
                file.write(chunk)

    def post_file(
        self, endpoint: str, path: Path, timeout_sec: float = 30
    ) -> None:
        """Submit a file to the server."""
        uri = urllib.parse.urljoin(self.server, endpoint)
        with path.open("rb") as file:
            files = {"file": (path.name, file, "application/x-gzip")}
            response = requests.post(uri, files=files, timeout=timeout_sec)
            response.raise_for_status()
