# Copyright (C) 2023-2024 Canonical
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
"""OIDC related views for authenticated application."""

import logging

from authlib.integrations.base_client.errors import (
    MismatchingStateError,
    OAuthError,
)
from flask import (
    Blueprint,
    current_app,
    redirect,
    session,
    url_for,
)

from testflinger.database import register_web_client

oidc_views = Blueprint("oidc", __name__)

logger = logging.getLogger(__name__)


@oidc_views.route("/callback")
def callback():
    """Redirect callback from OIDC Provider."""
    try:
        token = current_app.oauth.oidc.authorize_access_token()
        session["user"] = token["userinfo"]["name"]
        register_web_client(token)
    except (MismatchingStateError, OAuthError) as err:
        logger.warning("Oauth error during authentication: %s", str(err))
    return redirect(url_for("testflinger.home"))


@oidc_views.route("/login")
def login():
    """Redirects user to OIDC provider for authentication."""
    try:
        return current_app.oauth.oidc.authorize_redirect(
            redirect_uri=url_for("oidc.callback", _external=True)
        )
    except OAuthError:
        return redirect(url_for("testflinger.home"))


@oidc_views.route("/logout")
def logout():
    """Terminate user session and from the OIDC provider."""
    session.clear()
    return redirect(url_for("testflinger.home"))
