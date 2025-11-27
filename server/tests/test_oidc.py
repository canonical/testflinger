# Copyright (C) 2025 Canonical
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

"""Tests for the OIDC authenticated endpoints."""

from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from unittest.mock import Mock, patch

from authlib.common.security import generate_token
from flask import url_for

from testflinger.enums import ServerRoles


def test_login_redirects_to_oidc(oidc_app, iam_server):
    """Test login route redirects to OIDC provider."""
    app, _ = oidc_app
    client = app.test_client()

    # Mock OIDC provider redirection during login
    with app.test_request_context():
        response = client.get(url_for("oidc.login"))

    assert response.status_code == HTTPStatus.FOUND
    assert iam_server.url in response.location


def test_logout_clears_session(oidc_app, user):
    """Test logout clears session and redirects to home."""
    app, _ = oidc_app
    client = app.test_client()
    # Mock user is currently authenticated
    with client.session_transaction() as session:
        session["user"] = user.user_name

    # Mock OIDC provider redirection after logout
    with app.test_request_context():
        response = client.get(url_for("oidc.logout"))

        assert response.status_code == HTTPStatus.FOUND
        assert response.location == url_for("testflinger.home")

    # Validate there are no session information after logout
    with client.session_transaction() as session:
        assert "user" not in session


@patch("testflinger.oidc.views.current_app", new_callable=Mock)
def test_first_login_registers_new_client(mock_current_app, oidc_app, user):
    """Test successful login with OIDC provider registers new users."""
    app, mongo = oidc_app

    # Mock Oauth token
    mock_token = {
        "access_token": generate_token(48),
        "userinfo": {
            "sub": "1234",
            "name": user.user_name,
            "email": user.emails[0],
        },
    }

    # Mock authentication token return value
    mock_current_app.oauth.oidc.authorize_access_token.return_value = (
        mock_token
    )

    # Mock OIDC provider callback redirection after login
    client = app.test_client()
    with app.test_request_context():
        response = client.get(url_for("oidc.callback"))

        assert response.status_code == HTTPStatus.FOUND
        assert response.location == url_for("testflinger.home")

    # Validate new user was added
    web_client = mongo.web_clients.find_one(
        {"openid_sub": mock_token["userinfo"]["sub"]}
    )
    assert web_client["name"] == mock_token["userinfo"]["name"]
    assert web_client["email"] == mock_token["userinfo"]["email"]


@patch("testflinger.oidc.views.current_app", new_callable=Mock)
def test_client_refresh_login_if_exists(mock_current_app, oidc_app, user):
    """Test last login is updated if user exist and no new entry is added."""
    app, mongo = oidc_app

    created_time = last_login_time = datetime.now(timezone.utc) - timedelta(
        hours=1
    )

    client_entry = {
        "openid_sub": "1234",
        "email": user.emails[0],
        "name": user.user_name,
        "created_at": created_time,
        "last_login": last_login_time,
        "role": ServerRoles.CONTRIBUTOR,
    }

    # Mock Oauth token
    mock_token = {
        "access_token": generate_token(48),
        "userinfo": {
            "sub": "1234",
            "name": user.user_name,
            "email": user.emails[0],
        },
    }

    # Insert record directly into database
    mongo.web_clients.insert_one(client_entry)

    # Get the stored record for later comparison
    client_record = mongo.web_clients.find_one(
        {"openid_sub": mock_token["userinfo"]["sub"]}
    )

    # Mock authentication token return value
    mock_current_app.oauth.oidc.authorize_access_token.return_value = (
        mock_token
    )

    # Mock OIDC provider callback redirection after login
    client = app.test_client()
    with app.test_request_context():
        response = client.get(url_for("oidc.callback"))

        assert response.status_code == HTTPStatus.FOUND
        assert response.location == url_for("testflinger.home")

    web_client = mongo.web_clients.find_one(
        {"openid_sub": mock_token["userinfo"]["sub"]}
    )

    # Validate client remains the same and only last_login was updated
    assert mongo.web_clients.count_documents({}) == 1
    assert web_client["created_at"] == client_record["created_at"]
    # Check that last_login was updated
    assert (
        web_client["last_login"].replace(tzinfo=timezone.utc)
        != last_login_time
    )
