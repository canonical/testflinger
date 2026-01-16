# Copyright 2025 Canonical
# See LICENSE file for licensing details.

import base64
from pathlib import Path
from unittest.mock import MagicMock, patch

import common


@patch("os.chown")
@patch("os.chmod")
@patch("common.write_file")
def test_copy_ssh_keys(mock_write_file, mock_chmod, mock_chown):
    """Test the copy_ssh_keys function."""
    config = {
        "ssh-config": "ssh_config_content",
        "ssh-private-key": base64.b64encode(
            b"ssh_private_key_content"
        ).decode(),
        "ssh-public-key": base64.b64encode(b"ssh_public_key_content").decode(),
    }

    common.copy_ssh_keys(config)

    mock_write_file.assert_any_call(
        "/home/ubuntu/.ssh/id_rsa", "ssh_private_key_content"
    )
    mock_write_file.assert_any_call(
        "/home/ubuntu/.ssh/id_rsa.pub", "ssh_public_key_content"
    )
    assert mock_write_file.call_count == 3


@patch("common.Path.chmod")
@patch("common.Path.write_text")
@patch("common.Path.iterdir")
@patch("common.Path.read_text")
def test_update_charm_scripts(
    mock_read_text, mock_iterdir, mock_write_text, mock_chmod
):
    """Test update_charm_scripts renders and writes templates."""
    mock_script = MagicMock(spec=Path)
    mock_script.name = "test-script"
    mock_script.read_text.return_value = "config_dir={{ config_dir }}"
    mock_iterdir.return_value = [mock_script]

    config = {"config-dir": "my-agent-configs"}

    common.update_charm_scripts(config)

    mock_script.read_text.assert_called_once()
    mock_write_text.assert_called_once()
    mock_chmod.assert_called_once_with(0o775)
