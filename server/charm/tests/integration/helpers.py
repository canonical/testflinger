"""Helper functions for integration tests."""

import functools
import logging
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
import yaml
from requests.adapters import HTTPAdapter

logger = logging.getLogger(__name__)

METADATA = yaml.safe_load(Path("charmcraft.yaml").read_text(encoding="utf-8"))
APP_NAME = METADATA["name"]
MONGODB_CHARM = "mongodb-k8s"


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
            request.url = request.url.replace(  # type: ignore
                f"{result.scheme}://{result.hostname}",
                f"{result.scheme}://{self.ip}",
            )
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
    url = f"{base_url}/"
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
