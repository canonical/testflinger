# Copyright (C) 2025 Canonical Ltd.
"""Constants for the Testflinger CLI."""

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
