# Copyright 2025 Canonical
# See LICENSE file for licensing details.

import os
import unittest
from unittest.mock import MagicMock, mock_open, patch

from charm import TestflingerAgentHostCharm
from ops.testing import Harness

SUPERVISOR_CONF_DIR = "/etc/supervisor/conf.d"


class TestPortValidation(unittest.TestCase):
    """Test suite for process-based port validation and assignment logic."""

    def setUp(self):
        self.harness = Harness(TestflingerAgentHostCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()
        self.charm = self.harness.charm

    @patch("pathlib.Path.iterdir")
    @patch("pathlib.Path.exists")
    def test_get_supervisor_agents_port_mapping(
        self, mock_exists, mock_iterdir
    ):
        """Test getting configured agents from supervisor config files."""
        mock_exists.return_value = True

        # Create mock Path objects for the config files
        mock_agent1_path = MagicMock()
        mock_agent1_path.suffix = ".conf"
        mock_agent1_path.__str__ = MagicMock(
            return_value=f"{SUPERVISOR_CONF_DIR}/agent1.conf"
        )

        mock_agent2_path = MagicMock()
        mock_agent2_path.suffix = ".conf"
        mock_agent2_path.__str__ = MagicMock(
            return_value=f"{SUPERVISOR_CONF_DIR}/agent2.conf"
        )

        mock_other_path = MagicMock()
        mock_other_path.suffix = ".txt"

        mock_iterdir.return_value = [
            mock_agent1_path,
            mock_agent2_path,
            mock_other_path,
        ]

        test_data_dir = os.path.join(os.path.dirname(__file__), "test_data")

        with open(os.path.join(test_data_dir, "agent1.conf"), "r") as f:
            agent1_config = f.read()
        with open(os.path.join(test_data_dir, "agent2.conf"), "r") as f:
            agent2_config = f.read()

        config_files = {
            f"{SUPERVISOR_CONF_DIR}/agent1.conf": agent1_config,
            f"{SUPERVISOR_CONF_DIR}/agent2.conf": agent2_config,
        }

        def mock_open_file(filename, mode="r", encoding=None):
            if str(filename) in config_files:
                return mock_open(read_data=config_files[str(filename)])()
            raise FileNotFoundError()

        with patch("builtins.open", mock_open_file):
            mapping = self.charm.get_supervisor_agents_port_mapping()

        expected = {"agent1": 8000, "agent2": 8001}
        self.assertEqual(mapping, expected)

    def test_parse_supervisor_config_file_invalid(self):
        """Test parsing invalid supervisor config file."""
        config_content = """
                        [program:invalid]
                        command=some-other-process
                        """

        with patch("builtins.open", mock_open(read_data=config_content)):
            agent_name, port = self.charm.parse_supervisor_config_file(
                f"{SUPERVISOR_CONF_DIR}/invalid.conf"
            )
            self.assertIsNone(agent_name)
            self.assertIsNone(port)

    def test_parse_supervisor_config_file_missing_port(self):
        """Test parsing config file with testflinger-agent but no port."""
        test_data_dir = os.path.join(os.path.dirname(__file__), "test_data")
        with open(os.path.join(test_data_dir, "agent_no_port.conf"), "r") as f:
            config_content = f.read()

        with patch("builtins.open", mock_open(read_data=config_content)):
            agent_name, port = self.charm.parse_supervisor_config_file(
                f"{SUPERVISOR_CONF_DIR}/agent-no-port.conf"
            )
            self.assertIsNone(agent_name)
            self.assertIsNone(port)

    def test_parse_supervisor_config_file_file_error(self):
        """Test parsing config file when file cannot be read."""
        with patch("builtins.open", side_effect=OSError("Permission denied")):
            agent_name, port = self.charm.parse_supervisor_config_file(
                f"{SUPERVISOR_CONF_DIR}/unreadable.conf"
            )
            self.assertIsNone(agent_name)
            self.assertIsNone(port)

    @patch("socket.socket")
    def test_find_available_port_success(self, mock_socket):
        """Test finding an available port successfully."""
        mock_sock = MagicMock()
        mock_socket.return_value.__enter__.return_value = mock_sock
        mock_sock.bind.return_value = None

        used_ports = set()
        port = self.charm.find_available_port(used_ports, 8000, 8010)
        self.assertEqual(port, 8000)
        mock_sock.bind.assert_called_once_with(("localhost", 8000))

    @patch("socket.socket")
    def test_find_available_port_skip_used(self, mock_socket):
        """Test finding port skips already used ports."""
        mock_sock = MagicMock()
        mock_socket.return_value.__enter__.return_value = mock_sock
        mock_sock.bind.return_value = None

        used_ports = {8000, 8001}
        port = self.charm.find_available_port(used_ports, 8000, 8010)
        self.assertEqual(port, 8002)
        mock_sock.bind.assert_called_once_with(("localhost", 8002))

    @patch("socket.socket")
    def test_find_available_port_exhausted(self, mock_socket):
        """Test when no ports are available in the range."""
        mock_sock = MagicMock()
        mock_socket.return_value.__enter__.return_value = mock_sock
        mock_sock.bind.side_effect = OSError()

        used_ports = set()
        with self.assertRaises(RuntimeError) as cm:
            self.charm.find_available_port(used_ports, 8000, 8002)

        self.assertIn("No available ports found", str(cm.exception))

    def test_assign_metrics_port_existing_agent(self):
        """Test assigning port to existing configured agent."""
        configured_agents = {"existing_agent": 8000}
        used_ports = {8000}

        port = self.charm.assign_metrics_port(
            "existing_agent", configured_agents, used_ports
        )

        self.assertEqual(port, 8000)

    @patch.object(TestflingerAgentHostCharm, "find_available_port")
    def test_assign_metrics_port_finds_new_port(self, mock_find_port):
        """Test port assignment finds new port for new agent."""
        mock_find_port.return_value = 8002

        configured_agents = {"agent1": 8000, "agent2": 8001}
        used_ports = {8000, 8001}
        port = self.charm.assign_metrics_port(
            "new_agent", configured_agents, used_ports
        )

        self.assertEqual(port, 8002)
        mock_find_port.assert_called_once_with(used_ports)

    @patch.object(
        TestflingerAgentHostCharm, "get_supervisor_agents_port_mapping"
    )
    def test_port_assignment_avoids_used_ports(self, mock_get_supervisor):
        """Test that port assignment avoids ports already in use."""
        mock_get_supervisor.return_value = {"agent2": 8001}

        used_ports = {8001}

        with patch("socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_socket.return_value.__enter__.return_value = mock_sock
            mock_sock.bind.return_value = None

            port = self.charm.assign_metrics_port(
                "new_agent", {"agent2": 8001}, used_ports
            )

            self.assertNotEqual(port, 8001)
