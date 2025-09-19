# Copyright (C) 2025 Canonical Ltd.
"""Tests for the helpers of Testflinger CLI."""

import textwrap
from pathlib import Path

import pytest

from testflinger_cli.consts import SNAP_NAME
from testflinger_cli.errors import SnapPrivateFileError
from testflinger_cli.helpers import (
    file_is_in_snap_private_dir,
    is_snap,
    parse_filename,
    pretty_yaml_dump,
)


def test_is_snap(monkeypatch):
    """Test the is_snap function."""
    monkeypatch.delenv("SNAP_NAME", raising=False)
    assert not is_snap()

    monkeypatch.setenv("SNAP_NAME", SNAP_NAME)
    assert is_snap()


def test_is_in_snap_private_dir():
    """Test the is_in_snap_private_dir function."""
    assert file_is_in_snap_private_dir(Path("/tmp/job.yaml"))
    assert not file_is_in_snap_private_dir(Path("/home/ubuntu/tmp/job.yaml"))


def test_parse_filename_snap_private(monkeypatch):
    """Test the parse_filename function."""
    # Raises exception if the file is in a snap-confined directory
    monkeypatch.setenv("SNAP_NAME", SNAP_NAME)
    with pytest.raises(SnapPrivateFileError):
        parse_filename("/tmp/job.yaml", check_snap_private_dir=True)

    # Test that you can override the check_snap_private_dir
    assert parse_filename(
        "/tmp/job.yaml", check_snap_private_dir=False
    ) == Path("/tmp/job.yaml")

    # Test that normal files are not affected
    assert parse_filename(
        "/home/ubuntu/tmp/job.yaml", check_snap_private_dir=True
    ) == Path("/home/ubuntu/tmp/job.yaml")


def test_parse_filename_stdin():
    """Test the parse_filename function with stdin."""
    assert parse_filename("-", parse_stdin=True) is None


def test_pretty_yaml_dump():
    """Test pretty yaml dumper dumps single/multi line strings correctly."""
    single_line = {"a": "some"}
    assert pretty_yaml_dump(single_line).strip() == "a: some"

    multiline = {"a": "some \nother\n"}
    result = textwrap.dedent(
        """
        a: |
            some
            other
        """
    )
    assert (
        pretty_yaml_dump(multiline, indent=4, default_flow_style=False).strip()
        == result.strip()
    )
