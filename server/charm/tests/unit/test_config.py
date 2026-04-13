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


def test_valid_webhook_endpoint():
    """Test that valid webhook endpoints are accepted."""
    config = TestflingerServerConfig(
        webhook_endpoint="https://test-observer-api.local/v1/test-executions/"
    )
    assert (
        config.webhook_endpoint
        == "https://test-observer-api.local/v1/test-executions/"
    )

    config = TestflingerServerConfig(
        webhook_endpoint="http://test-observer-api.local/v1/test-executions/"
    )
    assert (
        config.webhook_endpoint
        == "http://test-observer-api.local/v1/test-executions/"
    )


def test_invalid_webhook_endpoint():
    """Test that invalid webhook endpoints are rejected."""
    # Reject webhook endpoints that do not include protocol
    with pytest.raises(ValueError):
        TestflingerServerConfig(
            webhook_endpoint="test-observer-api.local/v1/test-executions/"
        )

    # Reject webhook endpoints that do not include path
    with pytest.raises(ValueError):
        TestflingerServerConfig(
            webhook_endpoint="https://test-observer-api.local"
        )

    # Reject webhook endpoints that include only root path
    with pytest.raises(ValueError):
        TestflingerServerConfig(
            webhook_endpoint="https://test-observer-api.local/"
        )

    # Reject webhook endpoints that does not include hostname
    with pytest.raises(ValueError):
        TestflingerServerConfig(
            webhook_endpoint="https:///v1/test-executions/"
        )
