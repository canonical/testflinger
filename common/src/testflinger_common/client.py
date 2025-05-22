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
        """Initialize the client."""
        if urllib.parse.urlparse(server).scheme not in ("http", "https"):
            raise ValueError("Server URL must start with http:// or https://")
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
    def token(self) -> Optional[str]:
        """Return the token for the client."""
        if not self.client_id or not self.client_secret:
            return None
        id_key_pair = f"{self.client_id}:{self.client_secret}"
        encoded_id_key_pair = base64.b64encode(id_key_pair.encode()).decode()
        headers = {"Authorization": f"Basic {encoded_id_key_pair}"}
        response = self.post("/v1/oauth2/token", headers=headers)
        return response.text

    @cached_property
    def auth_headers(self) -> Optional[dict]:
        """Create an authorization header for the client."""
        return {"Authorization": self.token} if self.token else None

    def get(
        self,
        endpoint: str,
        headers: Optional[dict] = None,
        params: Optional[dict] = None,
        json: Optional[dict] = None,
        files: Optional[dict] = None,
        stream: Optional[bool] = None,
        timeout_sec: float = 15,
    ) -> requests.Response:
        """Get data from the server."""
        url = urllib.parse.urljoin(self.server, endpoint)
        response = self.session.get(
            url,
            headers=headers,
            params=params,
            json=json,
            files=files,
            stream=stream,
            timeout=timeout_sec,
        )
        response.raise_for_status()
        return response

    def get_file(
        self, endpoint: str, path: Path, timeout_sec: float = 30
    ) -> None:
        """Get a file from the server."""
        response = self.get(endpoint, timeout_sec=timeout_sec, stream=True)
        with path.open("wb") as file:
            for chunk in response.iter_content(chunk_size=4096):
                file.write(chunk)

    def post(
        self,
        endpoint: str,
        headers: Optional[dict] = None,
        params: Optional[dict] = None,
        json: Optional[dict] = None,
        files: Optional[dict] = None,
        timeout_sec: float = 15,
    ) -> requests.Response:
        """Post data to the server."""
        url = urllib.parse.urljoin(self.server, endpoint)
        response = self.session.post(
            url,
            headers=headers,
            params=params,
            json=json,
            files=files,
            timeout=timeout_sec,
        )
        response.raise_for_status()
        return response

    def submit_job(self, job_data: dict) -> str:
        """Submit a test job to the server."""
        headers = self.auth_headers
        response = self.post("/v1/job", json=job_data, headers=headers)
        return response.json().get("job_id")

    def cancel_job(self, job_id: str) -> None:
        """Cancel a test job on the server."""
        self.post_job_action(job_id=job_id, action="cancel")

    def submit_job_attachments(
        self, job_id: str, tarball: Path, timeout_sec: float = 30
    ) -> None:
        """Submit a test job's attachments to the server."""
        endpoint = f"/v1/job/{job_id}/attachments"
        with tarball.open("rb") as file:
            files = {"file": (tarball.name, file, "application/x-gzip")}
            self.post(endpoint, files=files, timeout_sec=timeout_sec)

    def get_job_attachments(
        self, job_id: str, path: Path, timeout_sec: float = 600
    ) -> None:
        """Get the attachments of a test job."""
        endpoint = f"/v1/job/{job_id}/attachments"
        self.get_file(endpoint, path, timeout_sec=timeout_sec)

    def post_job_results(self, job_id: str, data: dict) -> None:
        """Post the results of a test job."""
        self.post(f"/v1/result/{job_id}", json=data, timeout_sec=30)

    def get_job_results(self, job_id: str) -> dict:
        """Get the results of a test job."""
        response = self.get(f"/v1/result/{job_id}")
        return response.json()

    def get_job_artifacts(
        self, job_id: str, path: Path, timeout_sec: float = 30
    ) -> None:
        """Get the artifacts of a test job."""
        endpoint = f"/v1/result/{job_id}/artifact"
        self.get_file(endpoint, path, timeout_sec=timeout_sec)

    def post_job_artifacts(self, job_id: str, tarball: Path) -> None:
        """Post the artifacts of a test job."""
        endpoint = f"/v1/result/{job_id}/artifact"
        with tarball.open("rb") as file:
            files = {"file": (tarball.name, file, "application/x-gzip")}
            self.post(endpoint, files=files, timeout_sec=30)

    def get_jobs(self, queues: list[str]) -> dict:
        """Get the list of jobs from the server.

        :param queues: List of queues to filter jobs by.
        """
        response = self.get("/v1/job", params={"queue": queues})
        return response.json()

    def get_job(self, job_id: str) -> dict:
        """Get the job definition for a specified ID."""
        response = self.get(f"/v1/job/{job_id}")
        return response.json()

    def get_job_status(self, job_id: str) -> str:
        """Get the status of a test job."""
        results = self.get_job_results(job_id)
        return results.get("job_state", "unknown")

    def get_job_position(self, job_id: str) -> int:
        """Get the position of a test job in the queue."""
        response = self.get(f"/v1/job/{job_id}/position")
        return int(response.text)

    def post_job_provision_logs(
        self, agent_id: str, job_id: str, exit_code: int, detail: str
    ) -> None:
        """Post the outcome of a test job's provision phase."""
        endpoint = f"/v1/agents/provision_logs/{agent_id}"
        data = {"job_id": job_id, "exit_code": exit_code, "detail": detail}
        self.post(endpoint, json=data, timeout_sec=30)

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
            raise ValueError("Webhook URL is required for job status update.")
        data = {
            "agent_id": agent_id,
            "job_queue": job_queue,
            "job_status_webhook": webhook,
            "events": events,
        }
        self.post(f"/v1/job/{job_id}/events", json=data, timeout_sec=30)

    def post_job_output(self, job_id: str, output: str) -> None:
        """Post the output of a test job."""
        data = {"output": output}
        self.post(f"/v1/job/{job_id}/output", json=data, timeout_sec=60)

    def get_job_output(self, job_id: str) -> str:
        """Get the latest output for a test job."""
        response = self.get(f"/v1/job/{job_id}/output")
        return response.text

    def get_job_serial_output(self, job_id: str) -> str:
        """Get the latest serial output for a test job."""
        response = self.get(f"/v1/job/{job_id}/serial_output")
        return response.text

    def post_queues(self, queues: dict[str, str]) -> None:
        """Post the advertised queues to the server.

        :param queues: Dictionary of queue name to queue description.
        """
        self.post("/v1/agents/queues", json=queues, timeout_sec=30)

    def get_queues(self) -> dict:
        """Get the advertised queues from the server."""
        response = self.get("/v1/agents/queues")
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
        self.post("/v1/agents/images", json=images)

    def get_queue_images(self, queue: str) -> dict:
        """Get the advertised images for a queue from the server."""
        response = self.get(f"/v1/agents/images/{queue}")
        return response.json()

    def get_queue_agents(self, queue: str) -> dict:
        """Get the list of all agents listening to a specified queue."""
        response = self.get(f"/v1/queues/{queue}/agents")
        return response.json()

    def get_queue_wait_times(self, queues: Optional[list[str]] = None) -> dict:
        """Get the wait times for a list of queues."""
        queues = queues or []
        response = self.get("/v1/queues/wait_times", params={"queue": queues})
        return response.json()

    def post_agent_data(self, agent_id: str, data: dict) -> None:
        """Post the agent data to the server.

        :param agent_id: The ID of the agent.
        :param data: The data to post.
        """
        self.post(f"/v1/agents/data/{agent_id}", json=data, timeout_sec=30)

    def post_job_action(self, job_id: str, action: str) -> None:
        """Post an action to a test job."""
        self.post(f"/v1/job/{job_id}/action", json={"action": action})
