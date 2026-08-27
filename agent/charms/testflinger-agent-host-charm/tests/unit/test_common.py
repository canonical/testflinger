# Copyright 2025 Canonical
# See LICENSE file for licensing details.
"""Unit tests for common module."""

import base64
import stat
from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

import pytest

import common
from config import TestflingerAgentConfig

SSH_PUBLIC_KEY = "/home/ubuntu/.ssh/id_rsa.pub"
SSH_PRIVATE_KEY = "/home/ubuntu/.ssh/id_rsa"


@patch("os.chown")
@patch("os.chmod")
@patch("common.write_file")
def test_copy_ssh_keys(mock_write_file, mock_chmod, mock_chown):
    """Test the copy_ssh_keys function."""
    config = TestflingerAgentConfig(
        ssh_config="ssh_config_content",
        ssh_private_key=base64.b64encode(b"ssh_private_key_content").decode(),
        ssh_public_key=base64.b64encode(b"ssh_public_key_content").decode(),
    )

    common.copy_ssh_keys(config)

    mock_write_file.assert_any_call(
        Path("/home/ubuntu/.ssh/config"), "ssh_config_content", chmod=0o640
    )
    mock_write_file.assert_any_call(
        Path(SSH_PRIVATE_KEY), "ssh_private_key_content", chmod=0o600
    )
    mock_write_file.assert_any_call(
        Path(SSH_PUBLIC_KEY), "ssh_public_key_content"
    )
    assert mock_write_file.call_count == 3


@patch("common.write_file")
@patch("common.Path.iterdir")
@patch("common.Path.read_text")
def test_update_charm_scripts(mock_read_text, mock_iterdir, mock_write_file):
    """Test update_charm_scripts renders and writes templates."""
    mock_script = MagicMock(spec=Path)
    mock_script.name = "test-script"
    mock_script.read_text.return_value = "config_dir={{ config_dir }}"
    mock_iterdir.return_value = [mock_script]

    config = TestflingerAgentConfig(config_dir="my-agent-configs")

    common.update_charm_scripts(config)

    mock_script.read_text.assert_called_once()
    mock_write_file.assert_called_once()
    _, _, kwargs = mock_write_file.mock_calls[0]
    assert kwargs.get("chmod") == 0o775


@patch("os.chown")
def test_write_file_creates_with_correct_content(mock_chown, tmp_path):
    """Test write_file writes the correct content to the target file."""
    target = tmp_path / "test.txt"
    common.write_file(target, "hello world")
    assert target.read_text() == "hello world"


@patch("os.chown")
def test_write_file_sets_correct_permissions_and_ownership(
    mock_chown, tmp_path
):
    """Test write_file applies the given chmod and sets proper ownership."""
    target = tmp_path / "test.txt"
    mode = 0o600
    common.write_file(target, "content", chmod=mode)
    assert stat.S_IMODE(target.stat().st_mode) == mode
    # ubuntu:ubuntu is uid:gid 1000:1000
    mock_chown.assert_called_once_with(ANY, 1000, 1000)


@patch("os.replace")
@patch("os.chown")
def test_write_file_is_atomic(mock_chown, mock_replace, tmp_path):
    """Test write_file uses os.replace for an atomic swap."""
    target = tmp_path / "test.txt"
    common.write_file(target, "content")
    tmp_file, dest = mock_replace.call_args[0]
    assert Path(tmp_file).parent == target.parent
    assert dest == target


@patch("os.replace", side_effect=OSError)
@patch("os.chown")
def test_write_file_handles_oserror_and_cleans_up(
    mock_chown, mock_replace, tmp_path
):
    """Test write_file cleans up temporary file on OSError."""
    target = tmp_path / "test.txt"
    with pytest.raises(OSError):
        common.write_file(target, "content")

    # Ensure the temporary file is cleaned up
    temp_files = list(tmp_path.glob("tmp*"))
    assert len(temp_files) == 0
