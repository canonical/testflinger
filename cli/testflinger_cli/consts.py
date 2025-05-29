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

ADVERTISED_QUEUES_MESSAGE = (
    "ATTENTION: This only shows a curated list of queues with "
    "descriptions, not ALL queues. If you can't find the queue you want "
    "to use, a job can still be submitted for queues not listed here.\n"
)
