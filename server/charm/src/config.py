# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.
"""Charm configuration."""

import base64
import binascii
from urllib.parse import urlparse

import pydantic

MONGO_CSFLE_KEY_LENGTH = 96  # bytes


class TestflingerServerConfig(pydantic.BaseModel):
    """Testflinger Server Charm configuration."""

    external_hostname: str = "testflinger.local"
    keepalive: int = 10
    max_pool_size: int = 100
    jwt_signing_key: str = ""
    jwt_leeway: int = 5
    testflinger_secrets_master_key: str = ""
    http_proxy: str = ""
    https_proxy: str = ""
    no_proxy: str = "localhost,127.0.0.1,::1"
    enable_proxyfix: bool = False
    webhook_url: str = "http://test-observer-api.local/"
    webhook_auth: str = ""
    web_secret_key: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_provider_issuer: str = ""

    @pydantic.field_validator("external_hostname")
    @classmethod
    def validate_external_hostname(cls, value):
        """Validate that external_hostname does not include HTTP scheme.

        Protocol to be used is defined by the ingress controller.
        """
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

        return value

    @pydantic.field_validator("oidc_provider_issuer")
    @classmethod
    def validate_oidc_provider_issuer(cls, value):
        """Validate oidc_provider_issuer includes a scheme and host."""
        if not value:
            return value

        parsed_oidc = urlparse(value)
        if parsed_oidc.scheme not in {"http", "https"}:
            raise ValueError(
                "oidc_provider_issuer must include protocol (http:// or https://)"
            )
        if not parsed_oidc.netloc:
            raise ValueError("oidc_provider_issuer must include a host")
        return value.rstrip("/")

    @pydantic.field_validator("testflinger_secrets_master_key")
    @classmethod
    def validate_csfle_master_key(cls, value):
        """Validate that the CSFLE master key is valid base64."""
        if value:
            try:
                key_bytes = base64.b64decode(value, validate=True)
            except (binascii.Error, ValueError) as error:
                raise ValueError(
                    "Invalid 'testflinger_secrets_master_key': "
                    "value is not valid base64"
                ) from error
            if len(key_bytes) != MONGO_CSFLE_KEY_LENGTH:
                raise ValueError(
                    "Invalid 'testflinger_secrets_master_key': "
                    f"decoded key must be {MONGO_CSFLE_KEY_LENGTH} bytes long"
                )
        return value

    @pydantic.model_validator(mode="after")
    def validate_oidc_config(self):
        """Validate required OIDC parameters are set if any are configured."""
        required_oidc_params = [
            self.oidc_client_id,
            self.oidc_provider_issuer,
            self.web_secret_key,
        ]
        if any(required_oidc_params) and not all(required_oidc_params):
            raise ValueError(
                "oidc_client_id, oidc_provider_issuer, and web_secret_key"
                " must all be set if any OIDC configuration is provided"
            )
        return self
