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

from apiflask import APIBlueprint
from authlib.integrations.base_client.errors import (
    MismatchingStateError,
    OAuthError,
)
from flask import (
    current_app,
    redirect,
    request,
    session,
    url_for,
)

from testflinger.database import register_oidc_client
from testflinger.owasp import OWASPLogger

oidc_views = APIBlueprint("oidc", __name__, enable_openapi=False)


@oidc_views.route("/callback")
def callback():
    """Redirect callback from OIDC Provider."""
    try:
        token = current_app.oauth.oidc.authorize_access_token()
        userinfo = token["userinfo"]
        session["user"] = userinfo["name"]
        register_oidc_client(userinfo)
        # Log successful OIDC authentication
        current_app.owasp_logger.authn_login_success(
            userid=userinfo["name"],
            description=(f"User {userinfo['name']} authenticated via OIDC"),
            **OWASPLogger.get_request_metadata(request),
        )
    except (MismatchingStateError, OAuthError) as err:
        # Log failed OIDC authentication
        current_app.owasp_logger.authn_login_fail(
            userid="unknown",
            description=(
                f"OIDC authentication failed: {type(err).__name__}; "
                f"Oauth error during authentication: {err}"
            ),
            **OWASPLogger.get_request_metadata(request),
        )
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
