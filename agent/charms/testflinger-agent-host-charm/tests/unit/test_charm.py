# Copyright 2024 Canonical
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

import base64
import unittest
from unittest.mock import mock_open, patch

from charm import TestflingerAgentHostCharm
from ops.testing import Harness


class TestCharm(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(TestflingerAgentHostCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()

    @patch("os.chown")
    @patch("os.chmod")
    @patch("shutil.move")
    @patch("git.Repo.clone_from")
    @patch("charm.TestflingerAgentHostCharm.write_file")
    @patch("charm.TestflingerAgentHostCharm.restart_agents")
    @patch("charm.TestflingerAgentHostCharm.supervisor_update")
    @patch("charm.TestflingerAgentHostCharm.write_supervisor_service_files")
    def test_copy_ssh_keys(
        self,
        _,
        __,
        ___,
        mock_write_file,
        mock_clone_from,
        mock_move,
        mock_chmod,
        mock_chown,
    ):
        """
        Test the copy_ssh_keys method.

        The commands like supervisorctl in write_supervisor_files,
        restart_agents, and supervisor_update won't work here and
        are mocked out, but are tested in the integration tests.
        """
        mock_clone_from.return_value = None
        mock_move.return_value = None
        self.harness.update_config(
            {
                "ssh-private-key": base64.b64encode(
                    b"ssh_private_key_content"
                ).decode(),
                "ssh-public-key": base64.b64encode(
                    b"ssh_public_key_content"
                ).decode(),
                "config-repo": "foo",
                "config-dir": "bar",
            }
        )
        mock_write_file.assert_any_call(
            "/home/ubuntu/.ssh/id_rsa", "ssh_private_key_content"
        )
        mock_write_file.assert_any_call(
            "/home/ubuntu/.ssh/id_rsa.pub", "ssh_public_key_content"
        )
        self.assertEqual(mock_write_file.call_count, 3)

    @patch("os.listdir")
    @patch("builtins.open", new_callable=mock_open, read_data="test data")
    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.chmod")
    def test_update_tf_cmd_scripts(
        self,
        mock_chmod,
        mock_write_text,
        mock_open,
        mock_listdir,
    ):
        """Test the update_tf_cmd_scripts method."""
        charm = self.harness.charm
        tf_cmd_scripts_files = ["tf-setup"]

        mock_listdir.side_effect = [tf_cmd_scripts_files]

        charm.update_tf_cmd_scripts()

        # Ensure it tried to write the file correctly
        mock_write_text.assert_any_call("test data")

    def test_blocked_on_no_config_repo(self):
        """Test the on_config_changed method with no config-repo."""
        self.harness.update_config(
            {"config-repo": "", "config-dir": "agent-configs"}
        )
        self.assertEqual(self.harness.charm.unit.status.name, "blocked")

    def test_blocked_on_no_config_dir(self):
        """Test the on_config_changed method with no config-dir."""
        self.harness.update_config(
            {
                "config-repo": "https://github.com/canonical/testflinger.git",
                "config-dir": "",
            }
        )
        self.assertEqual(self.harness.charm.unit.status.name, "blocked")
