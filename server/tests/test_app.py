# Copyright (C) 2016-2022 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
"""Unit tests for Testflinger flask app."""

import secrets
from http import HTTPStatus
from unittest.mock import patch

import pytest
from werkzeug.middleware.proxy_fix import ProxyFix

from testflinger.application import create_flask_app


def test_default_config(testapp):
    """Test default config settings."""
    app = testapp
    assert app.config.get("PROPAGATE_EXCEPTIONS") is True


def test_setup_mongo_fails_without_config():
    """Ensure setup_mongo fails without config."""
    with pytest.raises(SystemExit) as exc:
        create_flask_app()
    assert exc.value.code == "No MongoDB URI configured!"


def test_proxyfix_enabled(monkeypatch):
    """Ensure ProxyFix is enabled when ENABLE_PROXYFIX is true."""
    monkeypatch.setenv("ENABLE_PROXYFIX", "true")
    app = create_flask_app(type("", (), {"TESTING": True})())
    assert isinstance(app.wsgi_app, ProxyFix)


def test_proxyfix_disabled(testapp):
    """Ensure ProxyFix is disabled when ENABLE_PROXYFIX is not set."""
    assert not isinstance(testapp.wsgi_app, ProxyFix)


def test_metrics_not_served_on_main_app(monkeypatch):
    """Ensure /metrics is still served on the main app by the exporter."""
    secret_key = secrets.token_urlsafe(32)
    monkeypatch.setenv("JWT_SIGNING_KEY", secret_key)
    app = create_flask_app(type("", (), {"TESTING": True})())
    with app.test_client() as client:
        response = client.get("/metrics")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_metrics_server_starts_on_default_port(monkeypatch):
    """Ensure the metrics HTTP server is started on the default port (9090)."""
    secret_key = secrets.token_urlsafe(32)
    monkeypatch.setenv("JWT_SIGNING_KEY", secret_key)
    monkeypatch.delenv("METRICS_PORT", raising=False)
    with (
        patch("testflinger.application.setup_mongodb"),
        patch(
            "testflinger.application.metrics.start_http_server"
        ) as mock_start,
    ):
        create_flask_app(type("", (), {"TESTING": False})())
    mock_start.assert_called_once_with(9090)


def test_metrics_server_starts_on_configured_port(monkeypatch):
    """Ensure the metrics HTTP server respects the METRICS_PORT env var."""
    secret_key = secrets.token_urlsafe(32)
    monkeypatch.setenv("JWT_SIGNING_KEY", secret_key)
    monkeypatch.setenv("METRICS_PORT", "9191")
    with (
        patch("testflinger.application.setup_mongodb"),
        patch(
            "testflinger.application.metrics.start_http_server"
        ) as mock_start,
    ):
        create_flask_app(type("", (), {"TESTING": False})())
    mock_start.assert_called_once_with(9191)


def test_metrics_server_not_started_in_testing_mode(monkeypatch):
    """Ensure the metrics HTTP server is not started when TESTING=True."""
    secret_key = secrets.token_urlsafe(32)
    monkeypatch.setenv("JWT_SIGNING_KEY", secret_key)
    with patch(
        "testflinger.application.metrics.start_http_server"
    ) as mock_start:
        create_flask_app(type("", (), {"TESTING": True})())
    mock_start.assert_not_called()
