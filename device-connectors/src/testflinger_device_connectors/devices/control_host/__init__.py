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

"""Package for implementing control-host-driven device connectors.

Modules inheriting from the provided abstract class run their provisioning
procedures on a control host via its REST API. The provisioning logic lives on
the control host, and the connector serves as a pre-processing step, validating
the configuration and preparing the API arguments.
"""

import json
import logging
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests

from testflinger_device_connectors.devices import (
    DefaultDevice,
    ProvisioningError,
)

logger = logging.getLogger(__name__)

# should mirror `testflinger_agent.config.ATTACHMENTS_DIR`
ATTACHMENTS_DIR = "attachments"


class ControlHostConnector(ABC, DefaultDevice):
    """Abstract base class defining a common interface for
    control-host-driven device connectors.
    """

    PROVISION_METHOD = ""  # to be defined in the implementation
    CONNECTION_TIMEOUT = 30
    READ_TIMEOUT = 60 * 90
    REST_PORT = 8000
    # Backoff between SSE stream reconnects. The base delay is used when the
    # previous stream made progress (emitted >= 1 log entry); the delay
    # doubles (up to the cap) on consecutive reconnects that produced no new
    # log lines, to avoid hammering the control host when its stream keeps
    # dropping.
    SSE_RECONNECT_DELAY = 2
    SSE_RECONNECT_MAX_DELAY = 30

    def _api_post(self, endpoint: str, **kwargs) -> requests.Response:
        """Send a POST request to the control host REST API.

        :param endpoint: API endpoint path (e.g. "/api/v1/system/poweroff").
        :param kwargs: Additional keyword arguments passed to requests.post.
        :returns: The response object.
        :raises requests.RequestException: On any request failure.
        """
        url = (
            f"http://{self.config['control_host']}:{self.REST_PORT}{endpoint}"
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
            f"http://{self.config['control_host']}:{self.REST_PORT}{endpoint}"
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
            f"http://{self.config['control_host']}:{self.REST_PORT}{endpoint}"
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
        provision_data = self.job_data["provision_data"]
        self.READ_TIMEOUT = (
            provision_data.get("provisioning_timeout") or self.READ_TIMEOUT
        )

        (api_args, api_kwargs) = self._validate_configuration()
        self._run(*api_args, **api_kwargs)

        self._post_run_actions(args)

        logger.info("END provision")

    @abstractmethod
    def _validate_configuration(
        self,
    ) -> Tuple[Tuple, Dict[str, Any]]:
        """Validate the job config and data and prepare the arguments
        for the control host `provision` API.
        """
        raise NotImplementedError

    @staticmethod
    def _find_provision_attachment() -> Optional[Path]:
        """Return the provision attachment if one was uploaded, else None."""
        attachments_dir = Path.cwd() / ATTACHMENTS_DIR / "provision"
        try:
            return next(p for p in attachments_dir.iterdir() if p.is_file())
        except (FileNotFoundError, NotADirectoryError, StopIteration):
            return None

    def _run(self, *args, **kwargs):
        """Run the provisioning on the control host via the REST API.

        Submits a provisioning job, streams SSE logs in real time,
        and checks the final job status. When a provision attachment
        is present, the image is uploaded via the ``/multipart``
        endpoint; otherwise the request is sent as plain JSON.
        """
        # Always enforce identity fields from connector config.
        kwargs["agent_name"] = self.config["agent_name"]
        kwargs["cid"] = self.config.get("env", {}).get("CID")
        kwargs["device_ip"] = self.config["device_ip"]
        # Keep caller-provided script values and only fall back to config.
        # When the connector is run directly without the Testflinger server,
        # job JSON can provide script overrides in the provisioning payload.
        kwargs.setdefault("reboot_script", self.config["reboot_script"])
        kwargs.setdefault("poweron_script", self.config.get("poweron_script"))
        kwargs.setdefault(
            "poweroff_script", self.config.get("poweroff_script")
        )
        payload = {
            "method": self.PROVISION_METHOD,
            "args": list(args),
            "kwargs": kwargs,
        }

        attachment = self._find_provision_attachment()
        if attachment is not None:
            logger.info(
                "Uploading boot binary %s as multipart attachment",
                attachment.name,
            )
            with open(attachment, "rb") as boot_binary_file:
                resp = self._api_post(
                    "/api/v1/provision/multipart",
                    data={"request": json.dumps(payload)},
                    files={"boot_binary": boot_binary_file},
                    timeout=(
                        self.CONNECTION_TIMEOUT,
                        self.READ_TIMEOUT,
                    ),
                )
        else:
            resp = self._api_post("/api/v1/provision", json=payload)

        job = resp.json()
        job_id = job["job_id"]

        timeout = (self.CONNECTION_TIMEOUT, self.READ_TIMEOUT)
        reconnect_delay = self.SSE_RECONNECT_DELAY
        last_id: Optional[str] = None
        while True:
            headers = (
                {"Last-Event-ID": last_id} if last_id is not None else None
            )
            sse = self._api_get(
                f"/api/v1/provision/{job_id}/logs",
                stream=True,
                timeout=timeout,
                headers=headers,
            )
            with sse:
                (
                    emitted,
                    cursor_updated,
                    stream_last_id,
                ) = self._stream_sse_logs(sse)
            if cursor_updated:
                last_id = stream_last_id

            status = self._api_get(f"/api/v1/provision/{job_id}").json()
            if status["status"] == "running":
                logger.warning(
                    "SSE stream disconnected but job %s is still running,"
                    " reconnecting in %ds...",
                    job_id,
                    reconnect_delay,
                )
                time.sleep(reconnect_delay)
                if emitted:
                    reconnect_delay = self.SSE_RECONNECT_DELAY
                else:
                    reconnect_delay = min(
                        reconnect_delay * 2, self.SSE_RECONNECT_MAX_DELAY
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
    def _stream_sse_logs(
        response: requests.Response,
    ) -> Tuple[int, bool, Optional[str]]:
        """Parse and log Server-Sent Events from a streaming response.

        An SSE event ends with a blank line and may contain an ``id`` field
        and multiple ``data`` fields. The resume cursor advances only after
        its event's log payload has been handled successfully, so malformed
        data cannot cause a log entry to be skipped after reconnecting.

        :returns: ``(emitted, cursor_updated, last_id)`` — the number of log
            entries emitted, whether an event updated the resume cursor, and
            that cursor. A ``None`` cursor clears Last-Event-ID; an unchanged
            cursor means a reconnect must retain its previous value.
        """
        emitted = 0
        cursor_updated = False
        last_id: Optional[str] = None
        event_id: Optional[str] = None
        event_has_id = False
        data_lines: list[str] = []

        for line in response.iter_lines(decode_unicode=True):
            if line == "":
                if data_lines:
                    payload = "\n".join(data_lines)
                    try:
                        entry = json.loads(payload)
                    except json.JSONDecodeError:
                        logger.warning("Malformed SSE data: %s", payload)
                    else:
                        level_name = entry.get("level", "").upper()
                        log_level = getattr(logging, level_name, None)
                        if log_level is None:
                            logger.warning(
                                "Unknown log level '%s', defaulting to INFO",
                                entry.get("level", ""),
                            )
                            log_level = logging.INFO
                        logger.log(
                            log_level,
                            "[control-host] %s",
                            entry.get("message", payload),
                        )
                        emitted += 1
                        if event_has_id:
                            last_id = event_id
                            cursor_updated = True

                event_id = None
                event_has_id = False
                data_lines.clear()
                continue

            if line.startswith(":"):
                continue

            field, separator, value = line.partition(":")
            if not separator:
                continue
            if value.startswith(" "):
                value = value[1:]

            if field == "id":
                event_id = value or None
                event_has_id = True
            elif field == "data":
                data_lines.append(value)

        return emitted, cursor_updated, last_id

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
        """Run further actions after the control host API returns."""
