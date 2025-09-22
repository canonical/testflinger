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

import os

from apiflask import APIFlask
from authlib.integrations.flask_client import OAuth


def setup_oidc_config(tf_app: APIFlask):
    """Define OIDC configuration for web authentication.

    :param tf_app: Testflinger app to set configuration
    """
    tf_app.config["SECRET_KEY"] = os.environ.get("WEB_SECRET_KEY")
    tf_app.config["OIDC_CLIENT_ID"] = os.environ.get("OIDC_CLIENT_ID")
    tf_app.config["OIDC_CLIENT_SECRET"] = os.environ.get("OIDC_CLIENT_SECRET")
    tf_app.config["OIDC_PROVIDER_ISSUER"] = os.environ.get(
        "OIDC_PROVIDER_ISSUER"
    )


def app_register_oidc(tf_app: APIFlask) -> OAuth | None:
    """Register app with OIDC if provider is set.

    :param tf_app: Testflinger app to register with OIDC
    """
    setup_oidc_config(tf_app=tf_app)

    client_id = tf_app.config["OIDC_CLIENT_ID"]
    client_secret = tf_app.config["OIDC_CLIENT_SECRET"]
    issuer = tf_app.config["OIDC_PROVIDER_ISSUER"]
    secret_key = tf_app.config["SECRET_KEY"]

    # If provider is not set, app will run without web authentication
    if not all([client_id, client_secret, issuer, secret_key]):
        return None

    # Register app with OIDC provider based on configuration values
    oauth = OAuth(tf_app)
    oauth.register(
        "oidc",
        client_id=client_id,
        client_secret=client_secret,
        client_kwargs={
            "scope": "openid profile email",
        },
        server_metadata_url=f"{issuer}/.well-known/openid-configuration",
    )
    return oauth
