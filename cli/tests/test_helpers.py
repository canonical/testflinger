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


def test_prompt_for_queue_valid_input(monkeypatch):
    """Test prompt_for_queue returns valid queue from user input."""
    from testflinger_cli.helpers import prompt_for_queue

    # Mock the client and its method
    class MockClient:
        def get_queues(self):
            return {"queue1": "Description 1", "queue2": "Description 2"}

    client = MockClient()
    monkeypatch.setattr("builtins.input", lambda _: "queue1")

    result = prompt_for_queue(client)
    assert result == "queue1"


def test_prompt_for_queue_list_queues(monkeypatch, capsys):
    """Test prompt_for_queue lists available queues when '?' is entered."""
    from testflinger_cli.helpers import prompt_for_queue

    class MockClient:
        def get_queues(self):
            return {"queue1": "Description 1", "queue2": "Description 2"}

    client = MockClient()
    inputs = iter(["?", "queue1"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    result = prompt_for_queue(client)
    assert result == "queue1"
    captured = capsys.readouterr()
    assert "queue1" in captured.out
    assert "queue2" in captured.out


def test_prompt_for_queue_unknown_with_confirmation(monkeypatch):
    """Test prompt_for_queue allows unknown queue with user confirmation."""
    from testflinger_cli.helpers import prompt_for_queue

    class MockClient:
        def get_queues(self):
            return {"queue1": "Description 1"}

    client = MockClient()
    inputs = iter(["unknown_queue", "y"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    result = prompt_for_queue(client)
    assert result == "unknown_queue"


def test_prompt_for_queue_unknown_decline(monkeypatch):
    """Test prompt_for_queue rejects unknown queue if user declines."""
    from testflinger_cli.helpers import prompt_for_queue

    class MockClient:
        def get_queues(self):
            return {"queue1": "Description 1"}

    client = MockClient()
    inputs = iter(["unknown_queue", "n", "queue1"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    result = prompt_for_queue(client)
    assert result == "queue1"
