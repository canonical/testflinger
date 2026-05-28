# Copyright (C) 2026 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Helper functions for integration tests."""

import functools
import logging
import time
from urllib.parse import urlparse

import jubilant
import requests
from requests.adapters import HTTPAdapter

logger = logging.getLogger(__name__)


class DNSResolverHTTPAdapter(HTTPAdapter):
    """Simple DNS resolver for HTTP requests."""

    def __init__(self, hostname: str, ip: str, *args, **kwargs) -> None:
        """Initialize the dns resolver.

        :param hostname: The hostname to resolve.
        :param ip: The IP address to resolve to.
        """
        super().__init__(*args, **kwargs)
        self.hostname = hostname
        self.ip = ip

    def send(
        self,
        request,
        stream=False,
        timeout=None,
        verify=True,
        cert=None,
        proxies=None,
    ) -> requests.Response:
        """Wrap HTTPAdapter send to modify the outbound request.

        :param request: The HTTP request.
        :param stream: Whether to stream the response.
        :param timeout: The request timeout.
        :param verify: Whether to verify SSL certificates.
        :param cert: Client certificate.
        :param proxies: Proxies to use for the request.
        :return: The HTTP response.
        """
        result = urlparse(request.url)
        if (
            result.hostname == self.hostname
            and result.scheme in ("http", "https")
            and self.ip
        ):
            request.url = request.url.replace(
                f"{result.scheme}://{result.hostname}",
                f"{result.scheme}://{self.ip}",
            )
            request.headers["Host"] = self.hostname
            if result.scheme == "https":
                self.poolmanager.connection_pool_kw["server_hostname"] = (
                    self.hostname
                )
                self.poolmanager.connection_pool_kw["assert_hostname"] = (
                    self.hostname
                )
        elif result.hostname == self.hostname:
            self.poolmanager.connection_pool_kw.pop("server_hostname", None)
            self.poolmanager.connection_pool_kw.pop("assert_hostname", None)
        return super().send(request, stream, timeout, verify, cert, proxies)


def app_is_up(base_url: str, session: requests.Session | None = None) -> bool:
    """Check that the application is up.

    :param base_url: The base URL of the application.
    :param session: Optional requests session to use.
    :return: True if the application is up, False otherwise.
    """
    url = f"{base_url}/v1/"
    logger.info("Querying endpoint: %s", url)
    get = session.get if session else requests.get
    response = get(url, timeout=15, verify=False)
    return response.ok and "Testflinger Server" in response.text


def retry(retry_num: int, retry_sleep_sec: int) -> callable:
    """Retry function decorator.

    :param retry_num: Number of retries.
    :param retry_sleep_sec: Sleep time between retries in seconds.
    :return: Decorated function.
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for i in range(retry_num):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    if i >= retry_num - 1:
                        raise Exception(
                            f"Exceeded {retry_num} retries"
                        ) from exc
                    logger.error(
                        "func %s failure %d/%d: %s",
                        func.__name__,
                        i + 1,
                        retry_num,
                        exc,
                    )
                    time.sleep(retry_sleep_sec)

        return wrapper

    return decorator


def get_haproxy_ip(juju: jubilant.Juju) -> str:
    """Get the public IP address of the haproxy unit.

    :param juju: The Juju instance for the machine model.
    :return: The public IP address of the haproxy unit.
    """
    status = juju.status()
    return status.apps["haproxy"].units["haproxy/0"].public_address
