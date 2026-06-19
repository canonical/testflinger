# Copyright (C) 2024 Canonical
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

"""Package containing modules for control-host-driven device connectors.

Modules inheriting from the provided abstract class drive provisioning
procedures via the control host's ``/api/v1/phases`` REST contract. The
provisioning logic (validation, payload construction, data files) lives in
the control host service; the connector is a thin client that submits the
job data envelope and streams back the logs.
"""

import json
import logging
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

import requests

from testflinger_device_connectors.devices import (
    DefaultDevice,
    ProvisioningError,
)

logger = logging.getLogger(__name__)

# should mirror `testflinger_agent.config.ATTACHMENTS_DIR`
ATTACHMENTS_DIR = "attachments"

# Default REST port of the control host service.
CONTROL_HOST_REST_PORT = 8000

# Base path of the phases REST contract (nested under the provision API).
PHASES_ENDPOINT = "/api/v1/provision/phases"

# How long to wait for a best-effort pre_provision phase to complete.
PRE_PROVISION_TIMEOUT = 60


def pre_provision(config: dict) -> None:
    """Best-effort hardware preparation via the control host.

    POSTs a ``pre_provision`` phase and polls the job to completion with a
    short timeout. No-op when no ``control_host`` is configured; failures are
    logged and swallowed (same semantics as the old ``disconnect_usb_stick``).

    :param config: The device configuration dictionary.
    """
    control_host = config.get("control_host")
    if not control_host:
        return

    base = f"http://{control_host}:{CONTROL_HOST_REST_PORT}"
    try:
        resp = requests.post(
            f"{base}{PHASES_ENDPOINT}",
            json={"phase": "pre_provision", "data": {"config": config}},
            timeout=10,
        )
        resp.raise_for_status()
        job_id = resp.json()["job_id"]

        deadline = time.monotonic() + PRE_PROVISION_TIMEOUT
        while time.monotonic() < deadline:
            status_resp = requests.get(
                f"{base}{PHASES_ENDPOINT}/{job_id}", timeout=10
            )
            status_resp.raise_for_status()
            status = status_resp.json().get("status")
            if status != "running":
                if status != "completed":
                    logger.warning(
                        "pre_provision phase did not complete on %s: %s",
                        control_host,
                        status,
                    )
                return
            time.sleep(2)
        logger.warning("pre_provision phase timed out on %s", control_host)
    except Exception as exc:  # noqa: BLE001 - best-effort, never block provision
        logger.debug(
            "Could not run pre_provision on %s: %s", control_host, exc
        )


class ControlHostConnector(ABC, DefaultDevice):
    """Abstract base class defining a common interface for control-host-driven
    device connectors.
    """

    # Provisioning method advertised to the control host ("kvm"/"iot"/"oem").
    PROVISION_METHOD = ""  # to be defined in the implementation
    CONTROL_HOST_CONNECTION_TIMEOUT = 30
    CONTROL_HOST_READ_TIMEOUT = 60 * 90
    CONTROL_HOST_REST_PORT = CONTROL_HOST_REST_PORT

    def _api_post(self, endpoint: str, **kwargs) -> requests.Response:
        """Send a POST request to the control host REST API.

        :param endpoint: API endpoint path (e.g. "/api/v1/phases").
        :param kwargs: Additional keyword arguments passed to requests.post.
        :returns: The response object.
        :raises requests.RequestException: On any request failure.
        """
        url = (
            f"http://{self.config['control_host']}"
            f":{self.CONTROL_HOST_REST_PORT}{endpoint}"
        )
        logger.info("POST %s", url)
        timeout = kwargs.pop("timeout", 30)
        response = requests.post(url, timeout=timeout, **kwargs)
        response.raise_for_status()
        return response

    def _api_get(self, endpoint: str, **kwargs) -> requests.Response:
        """Send a GET request to the control host REST API.

        :param endpoint: API endpoint path.
        :param kwargs: Additional keyword arguments passed to requests.get.
        :returns: The response object.
        :raises requests.RequestException: On any request failure.
        """
        url = (
            f"http://{self.config['control_host']}"
            f":{self.CONTROL_HOST_REST_PORT}{endpoint}"
        )
        logger.info("GET %s", url)
        timeout = kwargs.pop("timeout", 30)
        response = requests.get(url, timeout=timeout, **kwargs)
        response.raise_for_status()
        return response

    def _api_put(self, endpoint: str, **kwargs) -> requests.Response:
        """Send a PUT request to the control host REST API.

        :param endpoint: API endpoint path.
        :param kwargs: Additional keyword arguments passed to requests.put.
        :returns: The response object.
        :raises requests.RequestException: On any request failure.
        """
        url = (
            f"http://{self.config['control_host']}"
            f":{self.CONTROL_HOST_REST_PORT}{endpoint}"
        )
        logger.info("PUT %s", url)
        timeout = kwargs.pop("timeout", 30)
        response = requests.put(url, timeout=timeout, **kwargs)
        response.raise_for_status()
        return response

    def provision(self, args):
        """Provision device when the command is invoked."""
        super().provision(args)

        with open(args.job_data, encoding="utf-8") as job_json:
            self.job_data = json.load(job_json)

        logger.info("BEGIN provision")
        logger.info("Provisioning device")

        provision_data = self.job_data.get("provision_data", {})
        self.CONTROL_HOST_READ_TIMEOUT = provision_data.get(
            "provisioning_timeout",
            provision_data.get(
                "zapper_provisioning_timeout",
                self.CONTROL_HOST_READ_TIMEOUT,
            ),
        )

        self._run()

        self._post_run_actions(args)

        logger.info("END provision")

    def _read_agent_ssh_public_key(self) -> Optional[str]:
        """Return the agent's SSH public key, or None if it cannot be read.

        A missing key file is tolerated: the field is omitted from the
        provision envelope and a warning is logged.
        """
        try:
            return (
                Path("~/.ssh/id_rsa.pub")
                .expanduser()
                .read_text(encoding="utf-8")
            )
        except OSError as exc:
            logger.warning(
                "Could not read the agent's SSH public key: %s", exc
            )
            return None

    @staticmethod
    def _find_provision_attachment() -> Optional[Path]:
        """Return the provision attachment if one was uploaded, else None."""
        attachments_dir = Path.cwd() / ATTACHMENTS_DIR / "provision"
        try:
            return next(p for p in attachments_dir.iterdir() if p.is_file())
        except (FileNotFoundError, NotADirectoryError, StopIteration):
            return None

    def _build_provision_data(self) -> dict:
        """Build the ``data`` envelope for a ``provision`` phase request."""
        data = {
            "provision_method": self.PROVISION_METHOD,
            "job_data": self.job_data,
            "agent_name": self.config["agent_name"],
            "device_ip": self.config["device_ip"],
            "reboot_script": self.config["reboot_script"],
            "cid": self.config.get("env", {}).get("CID"),
        }
        public_key = self._read_agent_ssh_public_key()
        if public_key is not None:
            data["agent_ssh_public_key"] = public_key
        return data

    def _run(self):
        """Run provisioning via the control host ``/api/v1/phases`` API.

        Submits a ``provision`` phase job, streams SSE logs in real time,
        and checks the final job status. When a provision attachment is
        present, the image is uploaded via the ``/multipart`` endpoint;
        otherwise the request is sent as plain JSON.
        """
        payload = {
            "phase": "provision",
            "data": self._build_provision_data(),
            "log_level": "INFO",
        }

        attachment = self._find_provision_attachment()
        if attachment is not None:
            logger.info(
                "Uploading boot binary %s as multipart attachment",
                attachment.name,
            )
            with open(attachment, "rb") as attachment_file:
                resp = self._api_post(
                    f"{PHASES_ENDPOINT}/multipart",
                    data={"request": json.dumps(payload)},
                    files={"attachment": attachment_file},
                    timeout=(
                        self.CONTROL_HOST_CONNECTION_TIMEOUT,
                        self.CONTROL_HOST_READ_TIMEOUT,
                    ),
                )
        else:
            resp = self._api_post(PHASES_ENDPOINT, json=payload)

        job = resp.json()
        job_id = job["job_id"]

        timeout = (
            self.CONTROL_HOST_CONNECTION_TIMEOUT,
            self.CONTROL_HOST_READ_TIMEOUT,
        )
        while True:
            sse = self._api_get(
                f"{PHASES_ENDPOINT}/{job_id}/logs",
                stream=True,
                timeout=timeout,
            )
            with sse:
                self._stream_sse_logs(sse)

            # Check job status after the SSE stream ends
            status = self._api_get(f"{PHASES_ENDPOINT}/{job_id}").json()
            if status["status"] == "running":
                logger.warning(
                    "SSE stream disconnected but job %s is still running,"
                    " reconnecting...",
                    job_id,
                )
                continue
            if status["status"] != "completed":
                raise ProvisioningError(
                    status.get(
                        "error",
                        "Provisioning failed for unknown reason.",
                    )
                )
            break

    @staticmethod
    def _stream_sse_logs(response: requests.Response) -> None:
        """Parse and log Server-Sent Events from a streaming response.

        The SSE protocol sends newline-delimited lines in the format:
            data: {"level": "INFO", "message": "..."}
        Empty lines act as event separators and are skipped.
        Lines not starting with "data: " (e.g. "event:", "retry:")
        are non-standard for this endpoint and logged as warnings.
        """
        sse_data_prefix = "data: "
        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            if not line.startswith(sse_data_prefix):
                logger.warning("Unexpected SSE line: %s", line)
                continue
            try:
                entry = json.loads(line[len(sse_data_prefix) :])
            except json.JSONDecodeError:
                logger.warning("Malformed SSE data: %s", line)
                continue
            level_name = entry.get("level", "").upper()
            log_level = getattr(logging, level_name, None)
            if log_level is None:
                logger.warning(
                    "Unknown log level '%s', defaulting to INFO",
                    entry.get("level", ""),
                )
                log_level = logging.INFO
            logger.log(
                log_level, "[control_host] %s", entry.get("message", line)
            )

    def _copy_ssh_id(self):
        """Copy the ssh id to the device."""
        logger.info("Copying the agent's SSH public key to the DUT.")

        try:
            test_username = self.job_data.get("test_data", {}).get(
                "test_username", "ubuntu"
            )
            test_password = self.job_data.get("test_data", {}).get(
                "test_password", "ubuntu"
            )
        except AttributeError:
            test_username = "ubuntu"
            test_password = "ubuntu"

        try:
            self.copy_ssh_key(
                self.config["device_ip"],
                test_username,
                test_password,
            )
        except RuntimeError as e:
            raise ProvisioningError(
                "Cannot copy the agent's SSH key to the DUT",
            ) from e

    @abstractmethod
    def _post_run_actions(self, args):
        """Run further actions after the control host returns successfully."""
