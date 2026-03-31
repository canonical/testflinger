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

"""Package containing modules for implementing Zapper-driven device connectors.

Modules inheriting from the provided abstract class will run Zapper-driven
provisioning procedures via Zapper API. The provisioning logic is implemented
in the Zapper codebase and the connector serves as a pre-processing step,
validating the configuration and preparing the API arguments.
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Tuple

import requests

from testflinger_device_connectors.devices import (
    DefaultDevice,
    ProvisioningError,
)

logger = logging.getLogger(__name__)


class ZapperConnector(ABC, DefaultDevice):
    """Abstract base class defining a common interface for Zapper-driven
    device connectors.
    """

    PROVISION_METHOD = ""  # to be defined in the implementation
    ZAPPER_CONNECTION_TIMEOUT = 30
    ZAPPER_READ_TIMEOUT = 60 * 90
    ZAPPER_REST_PORT = 8000

    def _api_post(self, endpoint: str, **kwargs) -> requests.Response:
        """Send a POST request to the Zapper REST API.

        :param endpoint: API endpoint path (e.g. "/api/v1/system/poweroff").
        :param kwargs: Additional keyword arguments passed to requests.post.
        :returns: The response object.
        :raises requests.RequestException: On any request failure.
        """
        url = (
            f"http://{self.config['control_host']}"
            f":{self.ZAPPER_REST_PORT}{endpoint}"
        )
        logger.info("POST %s", url)
        timeout = kwargs.pop("timeout", 30)
        response = requests.post(url, timeout=timeout, **kwargs)
        response.raise_for_status()
        return response

    def _api_get(self, endpoint: str, **kwargs) -> requests.Response:
        """Send a GET request to the Zapper REST API.

        :param endpoint: API endpoint path.
        :param kwargs: Additional keyword arguments passed to requests.get.
        :returns: The response object.
        :raises requests.RequestException: On any request failure.
        """
        url = (
            f"http://{self.config['control_host']}"
            f":{self.ZAPPER_REST_PORT}{endpoint}"
        )
        logger.info("GET %s", url)
        timeout = kwargs.pop("timeout", 30)
        response = requests.get(url, timeout=timeout, **kwargs)
        response.raise_for_status()
        return response

    def _api_put(self, endpoint: str, **kwargs) -> requests.Response:
        """Send a PUT request to the Zapper REST API.

        :param endpoint: API endpoint path.
        :param kwargs: Additional keyword arguments passed to requests.put.
        :returns: The response object.
        :raises requests.RequestException: On any request failure.
        """
        url = (
            f"http://{self.config['control_host']}"
            f":{self.ZAPPER_REST_PORT}{endpoint}"
        )
        logger.info("PUT %s", url)
        timeout = kwargs.pop("timeout", 30)
        response = requests.put(url, timeout=timeout, **kwargs)
        response.raise_for_status()
        return response

    @staticmethod
    def _check_rest_api_on_host(host: str) -> None:
        """Check if the host has an active Zapper REST API.

        :raises ConnectionError: If the API is not reachable.
        """
        try:
            url = f"http://{host}:{ZapperConnector.ZAPPER_REST_PORT}/health"
            resp = requests.get(url, timeout=3)
            resp.raise_for_status()
            logger.debug("The host %s has an available REST API", host)
        except requests.RequestException as e:
            raise ConnectionError from e

    @staticmethod
    def wait_ready(host: str, timeout: int = 60) -> None:
        """Wait for the Zapper REST API to become available on the host.

        :param host: The host to check for REST API availability.
        :param timeout: Maximum time to wait in seconds (default: 60).
        :raises TimeoutError: If the API is not available within the timeout.
        """
        logger.info("Waiting for the Zapper REST API on control host %s", host)
        DefaultDevice.wait_online(
            ZapperConnector._check_rest_api_on_host, host, timeout
        )

    @staticmethod
    def typecmux_set_state(host: str, state: str) -> None:
        """Set the typecmux state on a Zapper host via the REST API.

        :param host: The Zapper host to connect to.
        :param state: The state to set (e.g., "OFF", "DUT").
        """
        base = f"http://{host}:{ZapperConnector.ZAPPER_REST_PORT}"
        resp = requests.get(
            f"{base}/api/v1/addons/",
            params={"addon_type": "TYPEC_MUX"},
            timeout=10,
        )
        resp.raise_for_status()
        addons = resp.json()["addons"]
        if not addons:
            raise RuntimeError("No TYPEC_MUX addon found on Zapper")
        addr = addons[0]["addr"]
        resp = requests.put(
            f"{base}/api/v1/addons/{addr}/typecmux/state",
            json={"state": state},
            timeout=10,
        )
        resp.raise_for_status()
        logger.info("Set typecmux state to %s on %s", state, host)

    @staticmethod
    def disconnect_usb_stick(config: Dict[str, Any]) -> None:
        """Try to disconnect the USB stick.

        This is a non-blocking operation - if the Zapper is not available,
        we simply skip this step.

        :param config: The device configuration dictionary.
        """
        control_host = config.get("control_host")
        if not control_host:
            return

        try:
            ZapperConnector.wait_ready(control_host)
            ZapperConnector.typecmux_set_state(control_host, "OFF")
        except (TimeoutError, ConnectionError, Exception) as e:
            logger.debug(
                "Could not disconnect USB stick on %s: %s", control_host, e
            )

    def provision(self, args):
        """Provision device when the command is invoked."""
        super().provision(args)

        control_host = self.config["control_host"]
        try:
            ZapperConnector.wait_ready(control_host)
        except TimeoutError as e:
            raise ProvisioningError("Cannot reach the Zapper REST API") from e

        with open(args.job_data, encoding="utf-8") as job_json:
            self.job_data = json.load(job_json)

        logger.info("BEGIN provision")
        logger.info("Provisioning device")
        self.ZAPPER_READ_TIMEOUT = self.job_data["provision_data"].get(
            "zapper_provisioning_timeout",
            self.ZAPPER_READ_TIMEOUT,
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
        for the Zapper `provision` API.
        """
        raise NotImplementedError

    def _run(self, *args, **kwargs):
        """Run the Zapper provisioning via the REST API.

        Submits a provisioning job, streams SSE logs in real time,
        and checks the final job status.
        """
        kwargs.update(
            {
                "agent_name": self.config["agent_name"],
                "cid": self.config.get("env", {}).get("CID"),
                "device_ip": self.config["device_ip"],
                "reboot_script": self.config["reboot_script"],
            }
        )

        resp = self._api_post(
            "/api/v1/provision",
            json={
                "method": self.PROVISION_METHOD,
                "args": list(args),
                "kwargs": kwargs,
            },
        )
        job = resp.json()
        job_id = job["job_id"]

        timeout = (self.ZAPPER_CONNECTION_TIMEOUT, self.ZAPPER_READ_TIMEOUT)
        while True:
            sse = self._api_get(
                f"/api/v1/provision/{job_id}/logs",
                stream=True,
                timeout=timeout,
            )
            with sse:
                self._stream_sse_logs(sse)

            # Check job status after the SSE stream ends
            status = self._api_get(f"/api/v1/provision/{job_id}").json()
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
            logger.log(log_level, "[zapper] %s", entry.get("message", line))

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
        """Run further actions after Zapper API returns successfully."""
