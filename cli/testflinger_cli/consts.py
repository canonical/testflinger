# Copyright (C) 2025 Canonical Ltd.
"""Constants for the Testflinger CLI."""

import os

from strenum import StrEnum


class ServerRoles(StrEnum):
    """Define roles for restricted endpoints."""

    ADMIN = "admin"
    MANAGER = "manager"
    CONTRIBUTOR = "contributor"
    USER = "user"


SNAP_NAME = "testflinger-cli"
SNAP_PRIVATE_DIRS = [
    "/tmp",  # noqa: S108
]
# Set fallback if not running as snap e.g. local uv
SNAP_COMMON = os.environ.get("SNAP_COMMON", f"/tmp/{SNAP_NAME}/common")  # noqa: S108

LOG_FORMAT = (
    "%(levelname)s: %(asctime)s %(filename)s:%(lineno)d -- %(message)s"
)
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

TESTFLINGER_SERVER = "https://testflinger.canonical.com"
TESTFLINGER_ERROR_THRESHOLD = 3
