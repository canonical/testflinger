# Copyright 2024 Canonical
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

import unittest
import os
from unittest.mock import patch
from charm import TestflingerAgentHostCharm
from ops.testing import Harness


class TestCharm(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(TestflingerAgentHostCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()

    @patch("charm.TestflingerAgentHostCharm.write_file")
    @patch("charm.TestflingerAgentHostCharm.read_resource")
    def test_copy_ssh_keys(self, mock_read_resource, mock_write_file):
        """Test the copy_ssh_keys method"""
        charm = self.harness.charm
        mock_read_resource.side_effect = [
            "ssh_priv_key_content",
            "ssh_pub_key_content",
        ]

        charm.copy_ssh_keys()

        mock_read_resource.assert_any_call("ssh_priv_key")
        mock_read_resource.assert_any_call("ssh_pub_key")
        self.assertEqual(mock_read_resource.call_count, 2)

        mock_write_file.assert_any_call(
            "/home/ubuntu/.ssh/id_rsa", "ssh_priv_key_content"
        )
        mock_write_file.assert_any_call(
            "/home/ubuntu/.ssh/id_rsa.pub", "ssh_pub_key_content"
        )
        self.assertEqual(mock_write_file.call_count, 2)

    @patch("os.listdir")
    @patch("shutil.copy")
    @patch("os.chmod")
    def test_update_tf_cmd_scripts(
        self, mock_chmod, mock_copy, mock_listdir
    ):
        """Test the update_tf_cmd_scripts method"""
        charm = self.harness.charm
        tf_cmd_scripts_files = ["tf-script3", "tf-script4"]

        mock_listdir.side_effect = [tf_cmd_scripts_files]

        charm.update_tf_cmd_scripts()
        tf_cmd_dir = "src/tf-cmd-scripts/"
        usr_local_bin = "/usr/local/bin/"
        mock_copy.assert_any_call(
            os.path.join(tf_cmd_dir, "tf-script3"),
            usr_local_bin,
        )
        mock_copy.assert_any_call(
            os.path.join(tf_cmd_dir, "tf-script4"),
            usr_local_bin,
        )
        self.assertEqual(mock_copy.call_count, 2)
        mock_chmod.assert_any_call(
            os.path.join(usr_local_bin, "tf-script3"), 0o775
        )
        mock_chmod.assert_any_call(
            os.path.join(usr_local_bin, "tf-script4"), 0o775
        )
        self.assertEqual(mock_chmod.call_count, 2)
