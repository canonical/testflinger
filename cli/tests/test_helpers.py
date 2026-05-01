# Copyright (C) 2025 Canonical Ltd.
"""Tests for the helpers of Testflinger CLI."""

import re
import textwrap
from argparse import ArgumentTypeError
from pathlib import Path
from unittest.mock import patch

import pytest

from testflinger_cli.consts import SNAP_NAME
from testflinger_cli.errors import SnapPrivateFileError
from testflinger_cli.helpers import (
    file_is_in_snap_private_dir,
    is_snap,
    parse_filename,
    pretty_yaml_dump,
    regex_arg,
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


@patch("builtins.input", return_value="queue1")
def test_prompt_for_queue_valid_input(mock_input):
    """Test prompt_for_queue returns valid queue from user input."""
    from testflinger_cli.helpers import prompt_for_queue

    queues = {"queue1": "Description 1", "queue2": "Description 2"}

    result = prompt_for_queue(queues)
    assert result == "queue1"


@patch("builtins.input", side_effect=["?", "queue1"])
def test_prompt_for_queue_list_queues(mock_input, capsys):
    """Test prompt_for_queue lists available queues when '?' is entered."""
    from testflinger_cli.helpers import prompt_for_queue

    queues = {"queue1": "Description 1", "queue2": "Description 2"}

    result = prompt_for_queue(queues)
    assert result == "queue1"
    captured = capsys.readouterr()
    assert "queue1" in captured.out
    assert "queue2" in captured.out


@patch("builtins.input", side_effect=["unknown_queue", "y"])
def test_prompt_for_queue_unknown_with_confirmation(mock_input):
    """Test prompt_for_queue allows unknown queue with user confirmation."""
    from testflinger_cli.helpers import prompt_for_queue

    queues = {"queue1": "Description 1"}

    result = prompt_for_queue(queues)
    assert result == "unknown_queue"


@patch("builtins.input", side_effect=["unknown_queue", "n", "queue1"])
def test_prompt_for_queue_unknown_decline(mock_input):
    """Test prompt_for_queue rejects unknown queue if user declines."""
    from testflinger_cli.helpers import prompt_for_queue

    queues = {"queue1": "Description 1"}

    result = prompt_for_queue(queues)
    assert result == "queue1"


def test_regex_arg_valid_pattern():
    """Test regex_arg compiles valid regex patterns."""
    pattern = regex_arg(r"test\d+")
    assert isinstance(pattern, re.Pattern)
    assert pattern.match("test123") is not None
    assert pattern.match("testxyz") is None


def test_regex_arg_simple_pattern():
    """Test regex_arg with simple pattern."""
    pattern = regex_arg("hello")
    assert isinstance(pattern, re.Pattern)
    assert pattern.search("hello world") is not None
    assert pattern.search("goodbye") is None


def test_regex_arg_complex_pattern():
    """Test regex_arg with complex regex pattern."""
    pattern = regex_arg(r"^[a-z]+@[a-z]+\.[a-z]+$")
    assert isinstance(pattern, re.Pattern)
    assert pattern.match("test@example.com") is not None
    assert pattern.match("invalid.email") is None


def test_regex_arg_invalid_pattern():
    """Test regex_arg raises ArgumentTypeError for invalid regex."""
    with pytest.raises(ArgumentTypeError) as exc_info:
        regex_arg(r"[invalid")
    assert "Invalid regex" in str(exc_info.value)
    assert "[invalid" in str(exc_info.value)


def test_regex_arg_empty_pattern():
    """Test regex_arg with empty pattern."""
    pattern = regex_arg("")
    assert isinstance(pattern, re.Pattern)
    assert pattern.search("anything") is not None
