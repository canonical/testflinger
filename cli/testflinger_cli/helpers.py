# Copyright (C) 2025 Canonical Ltd.
"""Helpers for the Testflinger CLI."""

from os import getenv
from pathlib import Path
from typing import Optional

from testflinger_cli.consts import SNAP_NAME, SNAP_PRIVATE_DIRS


def is_snap() -> bool:
    """Check if the current environment is in the Testflinger snap."""
    return getenv("SNAP_NAME") == SNAP_NAME


def file_is_in_snap_private_dir(file: Path) -> bool:
    """Check if the file is in a snap-confined directory."""
    return any(
        file.resolve().is_relative_to(path) for path in SNAP_PRIVATE_DIRS
    )


def parse_filename(
    filename: str,
    parse_stdin: bool = False,
    check_snap_private_dir: bool = True,
) -> Optional[Path]:
    """Parse the filename and return a Path object.

    :param filename:
        The filename to parse.
    :param parse_stdin:
        If True, treat "-" as stdin.
    :param check_snap_private_dir:
        If True, check if the file is in a snap-confined directory.
    :return:
        A Path object representing the filename. None if parse_stdin is True
        and filename is "-".
    :raises ValueError:
        If the file is in a snap-confined directory
        and check_snap_private_dir is True.
    """
    if parse_stdin and filename == "-":
        return None
    path = Path(filename)
    if (
        check_snap_private_dir
        and is_snap()
        and file_is_in_snap_private_dir(path)
    ):
        msg = f"File {path} is in a snap-confined directory."
        raise ValueError(msg)
    return path
