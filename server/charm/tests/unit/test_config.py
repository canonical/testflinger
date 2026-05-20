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
