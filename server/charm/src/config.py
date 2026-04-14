# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.
"""Charm configuration."""

from urllib.parse import urlparse

import pydantic

SSH_CONFIG_FILE = """\
StrictHostKeyChecking no
UserKnownHostsFile /dev/null
LogLevel QUIET
ConnectTimeout 30
"""


class TestflingerServerConfig(pydantic.BaseModel):
    """Testflinger Server Charm configuration."""

    external_hostname: str = "testflinger.local"
    keepalive: int = 10
    max_pool_size: int = 100
    jwt_signing_key: str = ""
    testflinger_secrets_master_key: str = ""
    http_proxy: str = ""
    https_proxy: str = ""
    no_proxy: str = "localhost,127.0.0.1,::1"
    webhook_url: str = "http://test-observer-api.local/"
    webhook_auth: str = ""

    @pydantic.field_validator("external_hostname")
    @classmethod
    def validate_external_hostname(cls, value):
        """Validate that external_hostname does not include protocol."""
        if value.startswith(("http://", "https://")):
            raise ValueError(
                "external_hostname must not include protocol (http:// or https://)"
            )
        return value

    @pydantic.field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, value):
        """Validate that webhook_url includes a protocol and no paths."""
        parsed_webhook = urlparse(value)
        if parsed_webhook.scheme not in {"http", "https"}:
            raise ValueError(
                "webhook_url must include protocol (http:// or https://)"
            )
        if not parsed_webhook.netloc:
            raise ValueError("webhook_url must include a host")
        if parsed_webhook.path not in {"", "/"}:
            raise ValueError("webhook_url must not include a path")

        return value
