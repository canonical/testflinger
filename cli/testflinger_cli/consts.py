# Copyright (C) 2025 Canonical Ltd.
"""Constants for the Testflinger CLI."""

from strenum import StrEnum


class ServerRoles(StrEnum):
    """Define roles for restricted endpoints."""

    ADMIN = "admin"
    MANAGER = "manager"
    CONTRIBUTOR = "contributor"
    AGENT = "agent"


SNAP_NAME = "testflinger-cli"
SNAP_PRIVATE_DIRS = [
    "/tmp",  # noqa: S108
]

LOG_FORMAT = (
    "%(levelname)s: %(asctime)s %(filename)s:%(lineno)d -- %(message)s"
)
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

TESTFLINGER_SERVER = "https://testflinger.canonical.com"
TESTFLINGER_ERROR_THRESHOLD = 3
