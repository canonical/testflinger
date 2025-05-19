# Copyright (C) 2025 Canonical Ltd.
"""Testflinger client module."""

import base64
import logging
import urllib.parse
from functools import cached_property
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class Client:
    """Testflinger client."""

    def __init__(
        self,
        server: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ) -> None:
        self.server = server
        self.client_id = client_id
        self.client_secret = client_secret

    @cached_property
    def token(self) -> str:
        """Return the token for the client."""
        if not self.client_id or not self.client_secret:
            return ""

        endpoint = "/v1/oauth2/token"
        id_key_pair = f"{self.client_id}:{self.client_secret}"
        encoded_id_key_pair = base64.b64encode(id_key_pair.encode()).decode()
        headers = {"Authorization": f"Basic {encoded_id_key_pair}"}
        response = self.post(endpoint=endpoint, data={}, headers=headers)
        return response.text

    @cached_property
    def auth_headers(self) -> Optional[dict]:
        """Create an authorization header for the client."""
        if not self.token:
            return None
        return {"Authorization": f"{self.token}"}

    def submit_job(self, job_data: dict) -> str:
        """Submit a test job to the server."""
        endpoint = "/v1/job"
        headers = self.auth_headers
        response = self.post(endpoint=endpoint, data=job_data, headers=headers)
        return response.json().get("job_id")

    def submit_job_attachment(
        self, job_id: str, path: Path, timeout_sec: float = 30
    ) -> None:
        """Submit a test job's attachment to the server."""
        endpoint = f"/v1/job/{job_id}/attachments"
        self.post_file(endpoint=endpoint, path=path, timeout_sec=timeout_sec)

    def get_job_results(self, job_id: str) -> dict:
        """Get the results of a test job."""
        endpoint = f"/v1/result/{job_id}"
        response = self.get(endpoint=endpoint)
        return response.json()

    def get_job_artifacts(self, job_id: str, path: Path) -> None:
        """Get the artifacts of a test job."""
        endpoint = f"/v1/result/{job_id}/artifact"
        self.get_file(endpoint=endpoint, path=path)

    def get_job(self, job_id: str) -> dict:
        """Get the job definition for a specified ID."""
        endpoint = f"/v1/job/{job_id}"
        response = self.get(endpoint=endpoint)
        return response.json()

    def get_job_status(self, job_id: str) -> str:
        """Get the status of a test job."""
        results = self.get_job_results(job_id)
        return results.get("job_state", "unknown")

    def get_job_position(self, job_id: str) -> int:
        """Get the position of a test job in the queue."""
        endpoint = f"/v1/job/{job_id}/position"
        response = self.get(endpoint=endpoint)
        return int(response.text)

    def get_job_output(self, job_id: str) -> str:
        """Get the latest output for a test job."""
        endpoint = f"/v1/job/{job_id}/output"
        response = self.get(endpoint=endpoint)
        return response.text

    def get_job_serial_output(self, job_id: str) -> str:
        """Get the latest serial output for a test job."""
        endpoint = f"/v1/job/{job_id}/serial_output"
        response = self.get(endpoint=endpoint)
        return response.text

    def get_queues(self) -> dict:
        """Get the advertised queues from the server."""
        endpoint = "/v1/agents/queues"
        response = self.get(endpoint=endpoint)
        return response.json()

    def get_queue_images(self, queue: str) -> dict:
        """Get the advertised images for a queue from the server."""
        endpoint = f"/v1/agents/images/{queue}"
        response = self.get(endpoint=endpoint)
        return response.json()

    def get_queue_agents(self, queue: str) -> dict:
        """Get the list of all agents listening to a specified queue."""
        endpoint = f"/v1/queues/{queue}/agents"
        response = self.get(endpoint=endpoint)
        return response.json()

    def get_queue_wait_times(self, queues: Optional[list[str]] = None) -> dict:
        """Get the wait times for a list of queues."""
        queues = queues or []
        endpoint = "/v1/queues/wait_times"
        params = {"queue": queues}
        response = self.get(endpoint=endpoint, params=params)
        return response.json()

    def get(
        self,
        endpoint: str,
        data: Optional[dict] = None,
        headers: Optional[dict] = None,
        params: Optional[dict] = None,
        timeout_sec: float = 15,
    ) -> requests.Response:
        """Submit a GET request to the server."""
        uri = urllib.parse.urljoin(self.server, endpoint)
        response = requests.get(
            uri, json=data, headers=headers, params=params, timeout=timeout_sec
        )
        response.raise_for_status()
        return response

    def post(
        self,
        endpoint: str,
        data: dict,
        headers: Optional[dict] = None,
        params: Optional[dict] = None,
        timeout_sec: float = 15,
    ) -> requests.Response:
        """Submit a POST request to the server."""
        uri = urllib.parse.urljoin(self.server, endpoint)
        response = requests.post(
            uri, json=data, headers=headers, params=params, timeout=timeout_sec
        )
        response.raise_for_status()
        return response

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
            for chunk in response.raw.stream(
                chunk_size=chunk_size, decode_content=False
            ):
                if chunk:
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
