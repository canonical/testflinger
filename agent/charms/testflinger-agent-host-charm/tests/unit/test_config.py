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


def test_invalid_base64_str_fields():
    """Test that invalid Base64Str fields raise errors."""
    with pytest.raises(ValueError):
        TestflingerAgentConfig(ssh_private_key="undecodable_string")

    with pytest.raises(ValueError):
        TestflingerAgentConfig(ssh_public_key="undecodable_string")


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


def test_container_tag_defaults_to_jammy():
    """Test that container_tag defaults to jammy."""
    assert TestflingerAgentConfig().container_tag == "jammy"


@pytest.mark.parametrize("tag", ["jammy", "noble"])
def test_valid_container_tag(tag):
    """Test that supported container tags are accepted."""
    assert TestflingerAgentConfig(container_tag=tag).container_tag == tag


@pytest.mark.parametrize("tag", ["", "focal", "latest", "jammy; rm -rf /"])
def test_invalid_container_tag(tag):
    """Test that unsupported container tags are rejected."""
    with pytest.raises(ValueError, match="container_tag must be one of"):
        TestflingerAgentConfig(container_tag=tag)
