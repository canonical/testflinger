"""Tests for the RealSerialLogger class."""

import socket
import unittest
from unittest import mock

from testflinger_device_connectors.devices import RealSerialLogger


class TestRealSerialLoggerStart(unittest.TestCase):
    """Test cases for the RealSerialLogger."""

    @mock.patch(
        "testflinger_device_connectors.devices.multiprocessing.Process"
    )
    def test_start_creates_daemon_process(self, mock_process):
        """Test that start creates a daemon process."""
        logger = RealSerialLogger("localhost", 8080, "test.log")
        mock_proc = mock.Mock()
        mock_process.return_value = mock_proc

        logger.start()

        mock_process.assert_called_once_with(
            target=logger._reconnector, daemon=True
        )
        mock_proc.start.assert_called_once()
        assert logger.proc == mock_proc

    @mock.patch("testflinger_device_connectors.devices.time.sleep")
    @mock.patch("testflinger_device_connectors.devices.logger")
    def test_reconnector_logs_error_once(self, mock_logger, mock_sleep):
        """Test that reconnector logs connection errors only once."""
        logger = RealSerialLogger("localhost", 8080, "test.log")

        with mock.patch.object(logger, "_log_serial") as mock_log_serial:
            mock_log_serial.side_effect = [
                socket.error("Connection failed"),
                socket.error("Connection failed again"),
                KeyboardInterrupt(),  # just a way to exit from while True
            ]

            with self.assertRaises(KeyboardInterrupt):
                logger._reconnector()

        mock_sleep.assert_called_with(30)
        mock_logger.error.assert_called_once_with(
            "Error connecting to serial logging server. "
            + "Retrying in the background..."
        )
