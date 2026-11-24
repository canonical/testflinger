# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.
"""Charm configuration."""

import ops
import pydantic

from defaults import DEFAULT_CONTAINER_TAG

SSH_CONFIG_FILE = """\
StrictHostKeyChecking no
UserKnownHostsFile /dev/null
LogLevel QUIET
ConnectTimeout 30
"""

SUPPORTED_CONTAINER_TAGS = {"jammy", "noble"}


class TestflingerAgentConfig(pydantic.BaseModel):
    """Testflinger Agent Host Charm configuration."""

    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    config_repo: str = ""
    config_branch: str = "main"
    config_dir: str = ""
    ssh_private_key: pydantic.Base64Str = ""
    ssh_public_key: pydantic.Base64Str = ""
    ssh_config: str = SSH_CONFIG_FILE
    testflinger_server: str = "https://testflinger.canonical.com"
    credentials_secret: ops.Secret | None = None
    container_tag: str = DEFAULT_CONTAINER_TAG

    @pydantic.field_validator("testflinger_server")
    @classmethod
    def validate_server(cls, value):
        """Validate testflinger_server config option includes a protocol."""
        if not value.startswith(("http://", "https://")):
            raise ValueError(
                "testflinger_server must include protocol (http:// or https://)"
            )
        return value

    @pydantic.field_validator("config_repo", "config_dir")
    @classmethod
    def validate_config_paths(cls, value):
        """Validate that both config_repo and config_dir have values."""
        if not value:
            raise ValueError("config_repo and config_dir must be set")
        return value

    @pydantic.field_validator("container_tag")
    @classmethod
    def validate_container_tag(cls, value):
        """Validate that the container tag is supported."""
        if value not in SUPPORTED_CONTAINER_TAGS:
            raise ValueError(
                f"container_tag must be one of {SUPPORTED_CONTAINER_TAGS}"
            )
        return value
