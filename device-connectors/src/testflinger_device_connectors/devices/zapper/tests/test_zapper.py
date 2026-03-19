# Copyright (C) 2024 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Unit tests for Zapper base device connector."""

import logging
import unittest
from unittest.mock import Mock, patch

import pytest
import requests

from testflinger_device_connectors.devices import ProvisioningError
from testflinger_device_connectors.devices.zapper import ZapperConnector


class MockConnector(ZapperConnector):
    PROVISION_METHOD = "Test"

    def _validate_configuration(self):
        return (), {}

    def _post_run_actions(self, args):
        pass


class ZapperConnectorTests(unittest.TestCase):
    """Unit tests for ZapperConnector class."""

    @patch("requests.get")
    @patch("requests.post")
    def test_run(self, mock_post, mock_get):
        """Test the `run` function submits a provisioning job via REST,
        streams SSE logs, and checks final status.
        """
        args = (1, 2, 3)
        kwargs = {"key1": 1, "key2": 2}

        fake_config = {
            "device_ip": "1.1.1.1",
            "agent_name": "my-agent",
            "control_host": "zapper-host",
            "reboot_script": ["cmd1", "cmd2"],
            "env": {"CID": "202507-01234"},
        }
        connector = MockConnector(fake_config)

        # Mock POST /api/v1/provision response
        mock_post.return_value.raise_for_status = Mock()
        mock_post.return_value.json.return_value = {"job_id": "job-123"}

        # Mock SSE stream (no log lines)
        mock_sse = Mock()
        mock_sse.iter_lines.return_value = []
        mock_sse.__enter__ = Mock(return_value=mock_sse)
        mock_sse.__exit__ = Mock(return_value=False)

        # Mock GET /api/v1/provision/job-123 (status check)
        mock_status = Mock()
        mock_status.raise_for_status = Mock()
        mock_status.json.return_value = {"status": "completed"}

        mock_get.side_effect = [mock_sse, mock_status]

        connector._run(*args, **kwargs)

        # Verify POST was called with correct provisioning payload
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        payload = call_kwargs[1]["json"]
        self.assertEqual(payload["method"], "Test")
        self.assertEqual(payload["args"], [1, 2, 3])
        self.assertIn("device_ip", payload["kwargs"])
        self.assertIn("agent_name", payload["kwargs"])

    def test_copy_ssh_id(self):
        """Test the function collects the device info from
        job and config and attempts to copy the agent SSH
        key to the DUT.
        """
        fake_config = {"device_ip": "1.1.1.1", "control_host": "zapper-host"}
        connector = MockConnector(fake_config)
        connector.job_data = {
            "test_data": {
                "test_username": "myuser",
                "test_password": "mypassword",
            }
        }
        connector.config = {"device_ip": "192.168.1.2"}

        connector.copy_ssh_key = Mock()
        connector._copy_ssh_id()

        connector.copy_ssh_key.assert_called_once_with(
            "192.168.1.2", "myuser", "mypassword"
        )

    def test_copy_ssh_id_raises(self):
        """Test the function raises a ProvisioningError exception
        in case of failure.
        """
        fake_config = {"device_ip": "1.1.1.1", "control_host": "zapper-host"}
        connector = MockConnector(fake_config)
        connector.job_data = {
            "test_data": {
                "test_username": "myuser",
                "test_password": "mypassword",
            }
        }
        connector.config = {"device_ip": "192.168.1.2"}

        connector.copy_ssh_key = Mock()
        connector.copy_ssh_key.side_effect = RuntimeError
        with self.assertRaises(ProvisioningError):
            connector._copy_ssh_id()


class TestZapperConnectorRestApiCheck:
    """Tests for ZapperConnector REST API health check."""

    def test_check_rest_api_on_host_success(self, mocker):
        """Test _check_rest_api_on_host succeeds when API is reachable."""
        mock_get = mocker.patch("requests.get")
        mock_get.return_value.raise_for_status = Mock()

        ZapperConnector._check_rest_api_on_host("test-host")

        mock_get.assert_called_once_with(
            "http://test-host:8000/health", timeout=3
        )

    def test_check_rest_api_on_host_raises_connection_error(self, mocker):
        """Test the function raises ConnectionError on failure."""
        mocker.patch(
            "requests.get",
            side_effect=requests.ConnectionError,
        )

        with pytest.raises(ConnectionError):
            ZapperConnector._check_rest_api_on_host("test-host")

    def test_check_rest_api_on_host_raises_on_timeout(self, mocker):
        """Test the function raises ConnectionError on timeout."""
        mocker.patch(
            "requests.get",
            side_effect=requests.Timeout,
        )

        with pytest.raises(ConnectionError):
            ZapperConnector._check_rest_api_on_host("test-host")

    def test_check_rest_api_on_host_raises_on_http_error(self, mocker):
        """Test the function raises ConnectionError on non-2xx response."""
        mock_get = mocker.patch("requests.get")
        mock_get.return_value.raise_for_status.side_effect = requests.HTTPError

        with pytest.raises(ConnectionError):
            ZapperConnector._check_rest_api_on_host("test-host")

    def test_wait_ready_success(self, mocker):
        """Test wait_ready calls wait_online with correct parameters."""
        from testflinger_device_connectors.devices import DefaultDevice

        mock_wait_online = mocker.patch.object(DefaultDevice, "wait_online")

        ZapperConnector.wait_ready("zapper-host", timeout=30)

        mock_wait_online.assert_called_once_with(
            ZapperConnector._check_rest_api_on_host, "zapper-host", 30
        )

    def test_wait_ready_timeout(self, mocker):
        """Test wait_ready raises TimeoutError when server unavailable."""
        from testflinger_device_connectors.devices import DefaultDevice

        mocker.patch.object(
            DefaultDevice, "wait_online", side_effect=TimeoutError
        )

        with pytest.raises(TimeoutError):
            ZapperConnector.wait_ready("zapper-host")


class TestZapperConnectorTypecmux:
    """Tests for ZapperConnector typecmux operations."""

    def test_typecmux_set_state_success(self, mocker):
        """Test typecmux_set_state queries addons and sets state via REST."""
        mock_get = mocker.patch("requests.get")
        mock_put = mocker.patch("requests.put")

        mock_get.return_value.raise_for_status = Mock()
        mock_get.return_value.json.return_value = {
            "addons": [{"addr": "0x42"}]
        }
        mock_put.return_value.raise_for_status = Mock()

        ZapperConnector.typecmux_set_state("zapper-host", "OFF")

        mock_get.assert_called_once_with(
            "http://zapper-host:8000/api/v1/addons/",
            params={"addon_type": "TYPEC_MUX"},
            timeout=10,
        )
        mock_put.assert_called_once_with(
            "http://zapper-host:8000/api/v1/addons/0x42/typecmux/state",
            json={"state": "OFF"},
            timeout=10,
        )

    def test_typecmux_set_state_no_addons(self, mocker):
        """Test typecmux_set_state raises when no TYPEC_MUX addon found."""
        mock_get = mocker.patch("requests.get")
        mock_get.return_value.raise_for_status = Mock()
        mock_get.return_value.json.return_value = {"addons": []}

        with pytest.raises(RuntimeError, match="No TYPEC_MUX addon"):
            ZapperConnector.typecmux_set_state("zapper-host", "OFF")

    def test_typecmux_set_state_with_dut(self, mocker):
        """Test typecmux_set_state with DUT state."""
        mock_get = mocker.patch("requests.get")
        mock_put = mocker.patch("requests.put")

        mock_get.return_value.raise_for_status = Mock()
        mock_get.return_value.json.return_value = {
            "addons": [{"addr": "0x42"}]
        }
        mock_put.return_value.raise_for_status = Mock()

        ZapperConnector.typecmux_set_state("zapper-host", "DUT")

        mock_put.assert_called_once_with(
            "http://zapper-host:8000/api/v1/addons/0x42/typecmux/state",
            json={"state": "DUT"},
            timeout=10,
        )


class TestZapperConnectorDisconnectUsbStick:
    """Tests for ZapperConnector USB stick disconnect functionality."""

    def test_disconnect_usb_stick_success(self, mocker):
        """Test disconnect_usb_stick succeeds when Zapper is available."""
        config = {"control_host": "zapper-host", "device_ip": "1.2.3.4"}

        mock_wait_ready = mocker.patch.object(ZapperConnector, "wait_ready")
        mock_typecmux = mocker.patch.object(
            ZapperConnector, "typecmux_set_state"
        )

        ZapperConnector.disconnect_usb_stick(config)

        mock_wait_ready.assert_called_once_with("zapper-host")
        mock_typecmux.assert_called_once_with("zapper-host", "OFF")

    def test_disconnect_usb_stick_no_control_host(self, mocker):
        """Test disconnect_usb_stick skips when no control_host."""
        config = {"device_ip": "1.2.3.4"}

        mock_wait_ready = mocker.patch.object(ZapperConnector, "wait_ready")
        mock_typecmux = mocker.patch.object(
            ZapperConnector, "typecmux_set_state"
        )

        ZapperConnector.disconnect_usb_stick(config)

        mock_wait_ready.assert_not_called()
        mock_typecmux.assert_not_called()

    def test_disconnect_usb_stick_timeout_non_blocking(self, mocker):
        """Test disconnect_usb_stick handles timeout gracefully."""
        config = {"control_host": "zapper-host", "device_ip": "1.2.3.4"}

        mocker.patch.object(
            ZapperConnector, "wait_ready", side_effect=TimeoutError
        )
        mock_typecmux = mocker.patch.object(
            ZapperConnector, "typecmux_set_state"
        )

        # Should not raise
        ZapperConnector.disconnect_usb_stick(config)

        mock_typecmux.assert_not_called()

    def test_disconnect_usb_stick_connection_error_non_blocking(self, mocker):
        """Test disconnect_usb_stick handles connection error gracefully."""
        config = {"control_host": "zapper-host", "device_ip": "1.2.3.4"}

        mocker.patch.object(
            ZapperConnector, "wait_ready", side_effect=ConnectionError
        )
        mock_typecmux = mocker.patch.object(
            ZapperConnector, "typecmux_set_state"
        )

        # Should not raise
        ZapperConnector.disconnect_usb_stick(config)

        mock_typecmux.assert_not_called()


class TestZapperConnectorRestApi:
    """Tests for ZapperConnector REST API client."""

    def test_api_post(self, mocker):
        """Test _api_post sends a POST request to the correct URL."""
        mock_post = mocker.patch("requests.post")
        mock_post.return_value.raise_for_status = Mock()

        connector = MockConnector({"control_host": "zapper-host"})
        connector._api_post("/api/v1/system/poweroff", timeout=10)

        mock_post.assert_called_once_with(
            "http://zapper-host:8000/api/v1/system/poweroff",
            timeout=10,
        )
        mock_post.return_value.raise_for_status.assert_called_once()

    def test_api_post_raises_on_http_error(self, mocker):
        """Test _api_post raises on HTTP error status."""
        mock_post = mocker.patch("requests.post")
        mock_post.return_value.raise_for_status.side_effect = (
            requests.HTTPError
        )

        connector = MockConnector({"control_host": "zapper-host"})
        with pytest.raises(requests.HTTPError):
            connector._api_post("/api/v1/system/poweroff")


class TestZapperConnectorRun:
    """Tests for ZapperConnector._run SSE streaming and job lifecycle."""

    @pytest.fixture()
    def connector(self):
        config = {
            "device_ip": "1.1.1.1",
            "agent_name": "my-agent",
            "control_host": "zapper-host",
            "reboot_script": ["cmd1"],
            "env": {"CID": "202507-01234"},
        }
        return MockConnector(config)

    @pytest.fixture()
    def mock_post(self, mocker):
        mock = mocker.patch("requests.post")
        mock.return_value.raise_for_status = Mock()
        mock.return_value.json.return_value = {"job_id": "job-123"}
        return mock

    def _make_sse(self, lines):
        """Create a mock SSE response context manager."""
        mock_sse = Mock()
        mock_sse.iter_lines.return_value = lines
        mock_sse.__enter__ = Mock(return_value=mock_sse)
        mock_sse.__exit__ = Mock(return_value=False)
        return mock_sse

    def test_run_uses_separate_connection_and_read_timeouts(
        self, mocker, connector, mock_post
    ):
        """Test that SSE streaming uses a (connect, read) timeout tuple."""
        mock_get = mocker.patch("requests.get")
        mock_sse = self._make_sse([])
        mock_status = Mock()
        mock_status.raise_for_status = Mock()
        mock_status.json.return_value = {"status": "completed"}
        mock_get.side_effect = [mock_sse, mock_status]

        connector._run()

        # First call is the SSE stream
        sse_call = mock_get.call_args_list[0]
        assert sse_call[1]["timeout"] == (
            connector.ZAPPER_CONNECTION_TIMEOUT,
            connector.ZAPPER_READ_TIMEOUT,
        )

    def test_run_streams_sse_log_lines(
        self, mocker, connector, mock_post, caplog
    ):
        """Test that valid SSE data lines are logged with [zapper] prefix
        at the correct level.
        """
        mock_get = mocker.patch("requests.get")

        lines = [
            'data: {"level": "INFO", "message": "Starting provisioning"}',
            'data: {"level": "WARNING", "message": "Disk space low"}',
        ]
        mock_sse = self._make_sse(lines)
        mock_status = Mock()
        mock_status.raise_for_status = Mock()
        mock_status.json.return_value = {"status": "completed"}
        mock_get.side_effect = [mock_sse, mock_status]

        with caplog.at_level(logging.DEBUG):
            connector._run()

        assert "[zapper] Starting provisioning" in caplog.text
        assert "[zapper] Disk space low" in caplog.text
        # Verify log levels are correct
        info_record = next(
            r for r in caplog.records if "Starting provisioning" in r.message
        )
        warn_record = next(
            r for r in caplog.records if "Disk space low" in r.message
        )
        assert info_record.levelno == logging.INFO
        assert warn_record.levelno == logging.WARNING

    def test_run_logs_unexpected_non_data_lines(
        self, mocker, connector, mock_post, caplog
    ):
        """Test that non-'data:' SSE lines are logged as warnings."""
        mock_get = mocker.patch("requests.get")

        lines = [
            "event: error",
            "retry: 3000",
            'data: {"level": "INFO", "message": "ok"}',
        ]
        mock_sse = self._make_sse(lines)
        mock_status = Mock()
        mock_status.raise_for_status = Mock()
        mock_status.json.return_value = {"status": "completed"}
        mock_get.side_effect = [mock_sse, mock_status]

        with caplog.at_level(logging.WARNING):
            connector._run()

        assert "Unexpected SSE line: event: error" in caplog.text
        assert "Unexpected SSE line: retry: 3000" in caplog.text

    def test_run_skips_empty_lines(self, mocker, connector, mock_post, caplog):
        """Test that empty SSE lines are silently skipped."""
        mock_get = mocker.patch("requests.get")

        lines = [
            "",
            'data: {"level": "INFO", "message": "ok"}',
            "",
        ]
        mock_sse = self._make_sse(lines)
        mock_status = Mock()
        mock_status.raise_for_status = Mock()
        mock_status.json.return_value = {"status": "completed"}
        mock_get.side_effect = [mock_sse, mock_status]

        with caplog.at_level(logging.WARNING):
            connector._run()

        assert "Unexpected SSE line" not in caplog.text

    def test_run_handles_malformed_json(
        self, mocker, connector, mock_post, caplog
    ):
        """Test that malformed JSON in SSE data is logged as a warning."""
        mock_get = mocker.patch("requests.get")

        lines = [
            "data: {not valid json",
            'data: {"level": "INFO", "message": "ok"}',
        ]
        mock_sse = self._make_sse(lines)
        mock_status = Mock()
        mock_status.raise_for_status = Mock()
        mock_status.json.return_value = {"status": "completed"}
        mock_get.side_effect = [mock_sse, mock_status]

        with caplog.at_level(logging.DEBUG):
            connector._run()

        assert "Malformed SSE data" in caplog.text
        assert "ok" in caplog.text

    def test_run_handles_missing_level_key(
        self, mocker, connector, mock_post, caplog
    ):
        """Test that a missing 'level' key defaults to INFO."""
        mock_get = mocker.patch("requests.get")

        lines = ['data: {"message": "no level here"}']
        mock_sse = self._make_sse(lines)
        mock_status = Mock()
        mock_status.raise_for_status = Mock()
        mock_status.json.return_value = {"status": "completed"}
        mock_get.side_effect = [mock_sse, mock_status]

        with caplog.at_level(logging.DEBUG):
            connector._run()

        assert "[zapper] no level here" in caplog.text
        record = next(
            r for r in caplog.records if "no level here" in r.message
        )
        assert record.levelno == logging.INFO

    def test_run_handles_missing_message_key(
        self, mocker, connector, mock_post, caplog
    ):
        """Test that a missing 'message' key falls back to raw line."""
        mock_get = mocker.patch("requests.get")

        raw_line = 'data: {"level": "INFO"}'
        lines = [raw_line]
        mock_sse = self._make_sse(lines)
        mock_status = Mock()
        mock_status.raise_for_status = Mock()
        mock_status.json.return_value = {"status": "completed"}
        mock_get.side_effect = [mock_sse, mock_status]

        with caplog.at_level(logging.INFO):
            connector._run()

        assert f"[zapper] {raw_line}" in caplog.text

    def test_run_handles_invalid_log_level(
        self, mocker, connector, mock_post, caplog
    ):
        """Test that an unrecognized log level warns and defaults to INFO."""
        mock_get = mocker.patch("requests.get")

        lines = ['data: {"level": "ERRROR", "message": "typo level"}']
        mock_sse = self._make_sse(lines)
        mock_status = Mock()
        mock_status.raise_for_status = Mock()
        mock_status.json.return_value = {"status": "completed"}
        mock_get.side_effect = [mock_sse, mock_status]

        with caplog.at_level(logging.DEBUG):
            connector._run()

        assert "Unknown log level 'ERRROR'" in caplog.text
        record = next(r for r in caplog.records if "typo level" in r.message)
        assert record.levelno == logging.INFO

    def test_run_handles_lowercase_log_level(
        self, mocker, connector, mock_post, caplog
    ):
        """Test that lowercase log levels are normalized with .upper()."""
        mock_get = mocker.patch("requests.get")

        lines = ['data: {"level": "warning", "message": "low case"}']
        mock_sse = self._make_sse(lines)
        mock_status = Mock()
        mock_status.raise_for_status = Mock()
        mock_status.json.return_value = {"status": "completed"}
        mock_get.side_effect = [mock_sse, mock_status]

        with caplog.at_level(logging.WARNING):
            connector._run()

        assert "[zapper] low case" in caplog.text
        record = next(r for r in caplog.records if "low case" in r.message)
        assert record.levelno == logging.WARNING

    def test_run_reconnects_when_job_still_running(
        self, mocker, connector, mock_post, caplog
    ):
        """Test that _run reconnects to SSE stream if the job is still
        running after a disconnection.
        """
        mock_get = mocker.patch("requests.get")

        # First SSE stream disconnects with partial logs
        sse_1 = self._make_sse(
            ['data: {"level": "INFO", "message": "step 1"}']
        )
        # Status check shows still running
        status_running = Mock()
        status_running.raise_for_status = Mock()
        status_running.json.return_value = {"status": "running"}

        # Second SSE stream delivers remaining logs
        sse_2 = self._make_sse(
            ['data: {"level": "INFO", "message": "step 2"}']
        )
        # Status check shows completed
        status_completed = Mock()
        status_completed.raise_for_status = Mock()
        status_completed.json.return_value = {"status": "completed"}

        mock_get.side_effect = [
            sse_1,
            status_running,
            sse_2,
            status_completed,
        ]

        with caplog.at_level(logging.DEBUG):
            connector._run()

        assert "step 1" in caplog.text
        assert "still running" in caplog.text
        assert "step 2" in caplog.text

    def test_run_raises_on_failed_status(self, mocker, connector, mock_post):
        """Test that _run raises ProvisioningError on non-completed status."""
        mock_get = mocker.patch("requests.get")

        mock_sse = self._make_sse([])
        mock_status = Mock()
        mock_status.raise_for_status = Mock()
        mock_status.json.return_value = {
            "status": "failed",
            "error": "Device unreachable",
        }
        mock_get.side_effect = [mock_sse, mock_status]

        with pytest.raises(ProvisioningError, match="Device unreachable"):
            connector._run()

    def test_run_raises_with_default_message_on_missing_error(
        self, mocker, connector, mock_post
    ):
        """Test that a missing 'error' key uses a default error message."""
        mock_get = mocker.patch("requests.get")

        mock_sse = self._make_sse([])
        mock_status = Mock()
        mock_status.raise_for_status = Mock()
        mock_status.json.return_value = {"status": "failed"}
        mock_get.side_effect = [mock_sse, mock_status]

        with pytest.raises(
            ProvisioningError,
            match="Provisioning failed for unknown reason.",
        ):
            connector._run()
