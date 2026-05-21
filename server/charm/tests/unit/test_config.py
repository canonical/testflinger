# Copyright 2026 Canonical
# See LICENSE file for licensing details.
"""Unit tests for config.py."""

import pytest

from config import TestflingerServerConfig


def test_valid_external_hostname():
    """Test that valid external hostname are accepted."""
    config = TestflingerServerConfig(external_hostname="testflinger.local")
    assert config.external_hostname == "testflinger.local"

    config = TestflingerServerConfig(
        external_hostname="testflinger.canonical.com"
    )
    assert config.external_hostname == "testflinger.canonical.com"


def test_invalid_external_hostname():
    """Test that invalid external hostname are rejected."""
    # Protocol is defined by ingress controller
    # Reject hostnames that include protocol
    with pytest.raises(ValueError):
        TestflingerServerConfig(external_hostname="http://testflinger.local")

    with pytest.raises(ValueError):
        TestflingerServerConfig(external_hostname="https://testflinger.local")


def test_valid_webhook_url():
    """Test that valid webhook urls are accepted."""
    config = TestflingerServerConfig(
        webhook_url="https://test-observer-api.local/"
    )
    assert config.webhook_url == "https://test-observer-api.local/"

    config = TestflingerServerConfig(
        webhook_url="http://test-observer-api.local"
    )
    assert config.webhook_url == "http://test-observer-api.local"


def test_invalid_webhook_url():
    """Test that invalid webhook urls are rejected."""
    # Reject webhook url that do not include protocol
    with pytest.raises(ValueError):
        TestflingerServerConfig(webhook_url="test-observer-api.local")

    # Reject webhook url that does not include hostname
    with pytest.raises(ValueError):
        TestflingerServerConfig(webhook_url="https:///v1/test-executions/")


def test_valid_oidc_configuration():
    """Test that OIDC configuration is validated correctly."""
    # Valid OIDC config with all parameters set
    config = TestflingerServerConfig(
        oidc_client_id="client-id",
        oidc_client_secret="client-secret",  # noqa: S106
        oidc_provider_issuer="https://oidc-provider.local",
        web_secret_key="web-secret-key",  # noqa: S106
    )
    assert config.oidc_client_id == "client-id"
    assert config.oidc_client_secret == "client-secret"  # noqa: S105
    assert config.oidc_provider_issuer == "https://oidc-provider.local"
    assert config.web_secret_key == "web-secret-key"  # noqa: S105


def test_invalid_oidc_configuration():
    """Test that invalid OIDC configuration raises validation error."""
    # Missing web_secret_key
    with pytest.raises(ValueError):
        TestflingerServerConfig(
            oidc_client_id="client-id",
            oidc_client_secret="client-secret",  # noqa: S106
            oidc_provider_issuer="https://oidc-provider.local",
        )

    # Missing oidc_provider_issuer
    with pytest.raises(ValueError):
        TestflingerServerConfig(
            oidc_client_id="client-id",
            oidc_client_secret="client-secret",  # noqa: S106
            web_secret_key="web-secret-key",  # noqa: S106
        )

    # Missing oidc_client_secret
    with pytest.raises(ValueError):
        TestflingerServerConfig(
            oidc_client_id="client-id",
            oidc_provider_issuer="https://oidc-provider.local",
            web_secret_key="web-secret-key",  # noqa: S106
        )

    # Missing oidc_client_id
    with pytest.raises(ValueError):
        TestflingerServerConfig(
            oidc_client_secret="client-secret",  # noqa: S106
            oidc_provider_issuer="https://oidc-provider.local",
            web_secret_key="web-secret-key",  # noqa: S106
        )


def test_invalid_oidc_provider_issuer():
    """Test that invalid OIDC provider issuer raises validation error."""
    # Reject oidc_provider_issuer that do not include protocol
    with pytest.raises(ValueError):
        TestflingerServerConfig(
            oidc_client_id="client-id",
            oidc_client_secret="client-secret",  # noqa: S106
            oidc_provider_issuer="oidc-provider.local",
            web_secret_key="web-secret-key",  # noqa: S106
        )

    config = TestflingerServerConfig(
        oidc_client_id="client-id",
        oidc_client_secret="client-secret",  # noqa: S106
        oidc_provider_issuer="https://keycloak.example.com/realms/myrealm",
        web_secret_key="web-secret-key",  # noqa: S106
    )
    assert config.oidc_provider_issuer == "https://keycloak.example.com/realms/myrealm"

    config = TestflingerServerConfig(
        oidc_client_id="client-id",
        oidc_client_secret="client-secret",  # noqa: S106
        oidc_provider_issuer="https://oidc-provider.local/",
        web_secret_key="web-secret-key",  # noqa: S106
    )
    assert config.oidc_provider_issuer == "https://oidc-provider.local"

    # Reject oidc_provider_issuer that does not include hostname
    with pytest.raises(ValueError):
        TestflingerServerConfig(
            oidc_client_id="client-id",
            oidc_client_secret="client-secret",  # noqa: S106
            oidc_provider_issuer="https:///issuer",
            web_secret_key="web-secret-key",  # noqa: S106
        )
