# Copyright 2026 Canonical
# See LICENSE file for licensing details.
"""Unit tests for config.py."""

import base64

import pytest
from config import TestflingerAgentConfig


def test_base64_str_fields():
    """Test that Base64Str fields decode correctly."""
    private_key = base64.b64encode(b"ssh_private_key_content").decode()
    public_key = base64.b64encode(b"ssh_public_key_content").decode()
    config = TestflingerAgentConfig(
        ssh_private_key=private_key,
        ssh_public_key=public_key,
    )
    assert config.ssh_private_key == "ssh_private_key_content"
    assert config.ssh_public_key == "ssh_public_key_content"


def test_valid_testflinger_server():
    """Test that valid server URLs are accepted."""
    config = TestflingerAgentConfig(
        testflinger_server="https://testflinger.local"
    )
    assert config.testflinger_server == "https://testflinger.local"

    config = TestflingerAgentConfig(
        testflinger_server="http://testflinger.local"
    )
    assert config.testflinger_server == "http://testflinger.local"


def test_invalid_testflinger_server():
    """Test that invalid server URLs are rejected."""
    with pytest.raises(ValueError):
        TestflingerAgentConfig(testflinger_server="localhost:5000")
