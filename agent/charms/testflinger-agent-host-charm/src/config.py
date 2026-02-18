# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.
"""Charm configuration."""

import ops
import pydantic

SSH_CONFIG_FILE = """\
StrictHostKeyChecking no
UserKnownHostsFile /dev/null
LogLevel QUIET
ConnectTimeout 30
"""


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

    @pydantic.field_validator("testflinger_server")
    @classmethod
    def validate_server(cls, value):
        if not value.startswith(("http://", "https://")):
            raise ValueError("testflinger_server must be an HTTPS URL")
        return value
