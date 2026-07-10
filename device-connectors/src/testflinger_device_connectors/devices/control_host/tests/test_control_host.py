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
"""Unit tests for the control host base device connector."""

import json as _json
import logging
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

import pytest
import requests

from testflinger_device_connectors.devices import ProvisioningError
from testflinger_device_connectors.devices.control_host import (
    ControlHostConnector,
    pre_provision,
)


class MockConnector(ControlHostConnector):
    PROVISION_METHOD = "test"

    def _post_run_actions(self, args):
        pass


def test_does_not_manage_dut_power_during_reboot_by_default():
    """The base control host connector does NOT keep the DUT off while the
    control host reboots; individual variants (e.g. control_host_iot) opt in
    explicitly so that variants like control_host_kvm are unaffected.
    """
    assert ControlHostConnector.MANAGE_DUT_POWER_DURING_REBOOT is False


class ControlHostConnectorEnvelopeTests(unittest.TestCase):
    """Unit tests for the provision phase envelope construction."""

    def setUp(self):
        self._prev_cwd = os.getcwd()
        self._tmpdir = tempfile.TemporaryDirectory()
        os.chdir(self._tmpdir.name)

    def tearDown(self):
        os.chdir(self._prev_cwd)
        self._tmpdir.cleanup()

    @patch("requests.get")
    @patch("requests.post")
    def test_run_builds_provision_phase_envelope(self, mock_post, mock_get):
        """`_run` submits a `provision` phase to the phases endpoint with
        the data envelope built from job_data and config.
        """
        fake_config = {
            "device_ip": "1.1.1.1",
            "agent_name": "my-agent",
            "control_host": "control-host",
            "reboot_script": ["cmd1", "cmd2"],
            "poweron_script": ["poweron1"],
            "poweroff_script": ["poweroff1"],
            "env": {"CID": "202507-01234"},
        }
        connector = MockConnector(fake_config)
        connector.job_data = {"provision_data": {"url": "http://img"}}
        connector._read_agent_ssh_public_key = Mock(return_value="ssh-rsa KEY")

        mock_post.return_value.raise_for_status = Mock()
        mock_post.return_value.json.return_value = {"job_id": "job-123"}

        mock_sse = Mock()
        mock_sse.iter_lines.return_value = []
        mock_sse.__enter__ = Mock(return_value=mock_sse)
        mock_sse.__exit__ = Mock(return_value=False)
        mock_status = Mock()
        mock_status.raise_for_status = Mock()
        mock_status.json.return_value = {"status": "completed"}
        mock_get.side_effect = [mock_sse, mock_status]

        connector._run()

        mock_post.assert_called_once()
        call = mock_post.call_args
        assert call[0][0].endswith("/api/v1/provision/phases")
        payload = call[1]["json"]
        self.assertEqual(payload["phase"], "provision")
        self.assertEqual(payload["log_level"], "INFO")
        data = payload["data"]
        self.assertEqual(data["provision_method"], "test")
        self.assertEqual(data["job_data"], connector.job_data)
        # The whole device config is sent verbatim under `config`; the
        # control host reads routing/power fields (agent_name, device_ip,
        # reboot_script, poweron/off_script, env.CID, ...) out of it.
        self.assertEqual(data["config"], fake_config)
        self.assertEqual(data["agent_ssh_public_key"], "ssh-rsa KEY")
        # Config fields are no longer field-picked to the top level.
        for key in (
            "agent_name",
            "device_ip",
            "reboot_script",
            "poweron_script",
            "poweroff_script",
            "cid",
        ):
            self.assertNotIn(key, data)

    @patch("requests.get")
    @patch("requests.post")
    def test_run_omits_pubkey_when_unavailable(self, mock_post, mock_get):
        """When the agent SSH public key cannot be read, the field is
        omitted from the envelope (not sent as None).
        """
        connector = MockConnector(
            {
                "device_ip": "1.1.1.1",
                "agent_name": "my-agent",
                "control_host": "control-host",
                "reboot_script": [],
            }
        )
        connector.job_data = {"provision_data": {}}
        connector._read_agent_ssh_public_key = Mock(return_value=None)

        mock_post.return_value.raise_for_status = Mock()
        mock_post.return_value.json.return_value = {"job_id": "job-123"}
        mock_sse = Mock()
        mock_sse.iter_lines.return_value = []
        mock_sse.__enter__ = Mock(return_value=mock_sse)
        mock_sse.__exit__ = Mock(return_value=False)
        mock_status = Mock()
        mock_status.json.return_value = {"status": "completed"}
        mock_get.side_effect = [mock_sse, mock_status]

        connector._run()

        data = mock_post.call_args[1]["json"]["data"]
        self.assertNotIn("agent_ssh_public_key", data)


def test_read_agent_ssh_public_key_reads_file(tmp_path, monkeypatch):
    """The pubkey is read from ~/.ssh/id_rsa.pub."""
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()
    (ssh_dir / "id_rsa.pub").write_text("ssh-rsa AAAA\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(tmp_path))

    connector = MockConnector({"control_host": "control-host"})
    assert connector._read_agent_ssh_public_key() == "ssh-rsa AAAA\n"


def test_read_agent_ssh_public_key_missing_returns_none(tmp_path, monkeypatch):
    """A missing key file logs a warning and returns None."""
    monkeypatch.setenv("HOME", str(tmp_path))
    connector = MockConnector({"control_host": "control-host"})
    assert connector._read_agent_ssh_public_key() is None


class ControlHostConnectorCopySshTests(unittest.TestCase):
    """Unit tests for _copy_ssh_id."""

    def test_copy_ssh_id(self):
        connector = MockConnector(
            {"device_ip": "1.1.1.1", "control_host": "control-host"}
        )
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
        connector = MockConnector(
            {"device_ip": "1.1.1.1", "control_host": "control-host"}
        )
        connector.job_data = {"test_data": {}}
        connector.config = {"device_ip": "192.168.1.2"}
        connector.copy_ssh_key = Mock(side_effect=RuntimeError)
        with self.assertRaises(ProvisioningError):
            connector._copy_ssh_id()


class TestControlHostConnectorRun:
    """Tests for ControlHostConnector._run SSE streaming and lifecycle."""

    @pytest.fixture(autouse=True)
    def _isolate_cwd(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

    @pytest.fixture()
    def connector(self):
        config = {
            "device_ip": "1.1.1.1",
            "agent_name": "my-agent",
            "control_host": "control-host",
            "reboot_script": ["cmd1"],
            "env": {"CID": "202507-01234"},
        }
        conn = MockConnector(config)
        conn.job_data = {"provision_data": {}}
        conn._read_agent_ssh_public_key = Mock(return_value="ssh-rsa KEY")
        return conn

    @pytest.fixture()
    def mock_post(self, mocker):
        mock = mocker.patch("requests.post")
        mock.return_value.raise_for_status = Mock()
        mock.return_value.json.return_value = {"job_id": "job-123"}
        return mock

    def _make_sse(self, lines):
        mock_sse = Mock()
        mock_sse.iter_lines.return_value = lines
        mock_sse.__enter__ = Mock(return_value=mock_sse)
        mock_sse.__exit__ = Mock(return_value=False)
        return mock_sse

    def _status(self, payload):
        mock_status = Mock()
        mock_status.raise_for_status = Mock()
        mock_status.json.return_value = payload
        return mock_status

    def test_run_uses_phases_logs_endpoint_and_timeouts(
        self, mocker, connector, mock_post
    ):
        mock_get = mocker.patch("requests.get")
        mock_get.side_effect = [
            self._make_sse([]),
            self._status({"status": "completed"}),
        ]

        connector._run()

        sse_call = mock_get.call_args_list[0]
        assert sse_call[0][0].endswith("/api/v1/provision/phases/job-123/logs")
        assert sse_call[1]["timeout"] == (
            connector.CONTROL_HOST_CONNECTION_TIMEOUT,
            connector.CONTROL_HOST_READ_TIMEOUT,
        )

    def test_run_streams_sse_log_lines(
        self, mocker, connector, mock_post, caplog
    ):
        mock_get = mocker.patch("requests.get")
        lines = [
            'data: {"level": "INFO", "message": "Starting provisioning"}',
            'data: {"level": "WARNING", "message": "Disk space low"}',
        ]
        mock_get.side_effect = [
            self._make_sse(lines),
            self._status({"status": "completed"}),
        ]
        with caplog.at_level(logging.DEBUG):
            connector._run()
        assert "[control_host] Starting provisioning" in caplog.text
        assert "[control_host] Disk space low" in caplog.text
        warn_record = next(
            r for r in caplog.records if "Disk space low" in r.message
        )
        assert warn_record.levelno == logging.WARNING

    def test_run_logs_unexpected_non_data_lines(
        self, mocker, connector, mock_post, caplog
    ):
        mock_get = mocker.patch("requests.get")
        mock_get.side_effect = [
            self._make_sse(["event: error", "retry: 3000"]),
            self._status({"status": "completed"}),
        ]
        with caplog.at_level(logging.WARNING):
            connector._run()
        assert "Unexpected SSE line: event: error" in caplog.text

    def test_run_handles_malformed_json(
        self, mocker, connector, mock_post, caplog
    ):
        mock_get = mocker.patch("requests.get")
        mock_get.side_effect = [
            self._make_sse(["data: {not valid json"]),
            self._status({"status": "completed"}),
        ]
        with caplog.at_level(logging.DEBUG):
            connector._run()
        assert "Malformed SSE data" in caplog.text

    def test_run_reconnects_when_job_still_running(
        self, mocker, connector, mock_post, caplog
    ):
        mock_get = mocker.patch("requests.get")
        mock_get.side_effect = [
            self._make_sse(['data: {"level": "INFO", "message": "step 1"}']),
            self._status({"status": "running"}),
            self._make_sse(['data: {"level": "INFO", "message": "step 2"}']),
            self._status({"status": "completed"}),
        ]
        with caplog.at_level(logging.DEBUG):
            connector._run()
        assert "step 1" in caplog.text
        assert "still running" in caplog.text
        assert "step 2" in caplog.text

    def test_run_raises_on_failed_status(self, mocker, connector, mock_post):
        mock_get = mocker.patch("requests.get")
        mock_get.side_effect = [
            self._make_sse([]),
            self._status({"status": "failed", "error": "Device unreachable"}),
        ]
        with pytest.raises(ProvisioningError, match="Device unreachable"):
            connector._run()

    def test_run_raises_with_default_message_on_missing_error(
        self, mocker, connector, mock_post
    ):
        mock_get = mocker.patch("requests.get")
        mock_get.side_effect = [
            self._make_sse([]),
            self._status({"status": "failed"}),
        ]
        with pytest.raises(
            ProvisioningError, match="Provisioning failed for unknown reason."
        ):
            connector._run()

    def test_run_without_attachment_uses_json_endpoint(
        self, mocker, connector, mock_post
    ):
        mock_get = mocker.patch("requests.get")
        mock_get.side_effect = [
            self._make_sse([]),
            self._status({"status": "completed"}),
        ]
        connector._run()
        call = mock_post.call_args
        assert call[0][0].endswith("/api/v1/provision/phases")
        assert "json" in call[1]
        assert "files" not in call[1]

    def test_run_with_attachment_uses_multipart_endpoint(
        self, mocker, connector, mock_post, tmp_path
    ):
        attach_dir = tmp_path / "attachments" / "provision"
        attach_dir.mkdir(parents=True)
        (attach_dir / "image.img").write_bytes(b"fake image data")

        mock_get = mocker.patch("requests.get")
        mock_get.side_effect = [
            self._make_sse([]),
            self._status({"status": "completed"}),
        ]
        connector._run()

        call = mock_post.call_args
        assert call[0][0].endswith("/api/v1/provision/phases/multipart")
        assert "files" in call[1]
        assert "attachment" in call[1]["files"]
        payload = _json.loads(call[1]["data"]["request"])
        assert payload["phase"] == "provision"
        assert payload["data"]["provision_method"] == "test"


class TestControlHostReadTimeout:
    """Tests for read-timeout resolution from provision_data."""

    @pytest.fixture(autouse=True)
    def _isolate_cwd(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

    def _provision(self, mocker, tmp_path, provision_data):
        job_file = tmp_path / "job.json"
        job_file.write_text(_json.dumps({"provision_data": provision_data}))
        connector = MockConnector(
            {
                "device_ip": "1.1.1.1",
                "agent_name": "my-agent",
                "control_host": "control-host",
                "reboot_script": [],
            }
        )
        mocker.patch.object(connector, "pre_provision_hook")
        mocker.patch.object(connector, "_run")
        mocker.patch.object(connector, "_post_run_actions")
        args = Mock()
        args.job_data = str(job_file)
        connector.provision(args)
        return connector

    def test_read_timeout_from_generic_key(self, mocker, tmp_path):
        connector = self._provision(
            mocker, tmp_path, {"provisioning_timeout": 1234}
        )
        assert connector.CONTROL_HOST_READ_TIMEOUT == 1234

    def test_read_timeout_legacy_fallback(self, mocker, tmp_path):
        connector = self._provision(
            mocker, tmp_path, {"zapper_provisioning_timeout": 4321}
        )
        assert connector.CONTROL_HOST_READ_TIMEOUT == 4321

    def test_read_timeout_generic_wins(self, mocker, tmp_path):
        connector = self._provision(
            mocker,
            tmp_path,
            {"provisioning_timeout": 1, "zapper_provisioning_timeout": 2},
        )
        assert connector.CONTROL_HOST_READ_TIMEOUT == 1


class TestPreProvisionHelper:
    """Tests for the module-level best-effort pre_provision helper."""

    def test_no_control_host_is_noop(self, mocker):
        mock_post = mocker.patch("requests.post")
        pre_provision({"device_ip": "1.2.3.4"})
        mock_post.assert_not_called()

    def test_submits_pre_provision_phase_and_polls(self, mocker):
        mock_post = mocker.patch("requests.post")
        mock_post.return_value.raise_for_status = Mock()
        mock_post.return_value.json.return_value = {"job_id": "job-9"}
        mock_get = mocker.patch("requests.get")
        mock_get.return_value.raise_for_status = Mock()
        mock_get.return_value.json.return_value = {"status": "completed"}

        pre_provision({"control_host": "control-host", "device_ip": "1.2.3.4"})

        post_call = mock_post.call_args
        assert post_call[0][0].endswith("/api/v1/provision/phases")
        body = post_call[1]["json"]
        assert body["phase"] == "pre_provision"
        assert body["data"]["config"] == {
            "control_host": "control-host",
            "device_ip": "1.2.3.4",
        }
        assert mock_get.call_args[0][0].endswith(
            "/api/v1/provision/phases/job-9"
        )

    def test_swallows_exceptions(self, mocker):
        mocker.patch(
            "requests.post", side_effect=requests.ConnectionError("boom")
        )
        # Should not raise
        pre_provision({"control_host": "control-host"})

    def test_failed_phase_does_not_raise(self, mocker):
        mock_post = mocker.patch("requests.post")
        mock_post.return_value.raise_for_status = Mock()
        mock_post.return_value.json.return_value = {"job_id": "job-9"}
        mock_get = mocker.patch("requests.get")
        mock_get.return_value.raise_for_status = Mock()
        mock_get.return_value.json.return_value = {
            "status": "failed",
            "error": "no addon",
        }
        # Should not raise
        pre_provision({"control_host": "control-host"})
