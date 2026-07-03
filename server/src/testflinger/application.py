# Copyright (C) 2016-2023 Canonical
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
"""Setup the Testflinger web application."""

import logging
import os

from apiflask import APIFlask
from flask import request
from pymongo.errors import ConnectionFailure
from werkzeug.exceptions import NotFound
from werkzeug.middleware.proxy_fix import ProxyFix

from testflinger.api.v1 import LogTypeConverter, v1
from testflinger.database import setup_mongodb
from testflinger.extensions import metrics
from testflinger.oidc import app_register_oidc
from testflinger.oidc.api import oidc_api
from testflinger.oidc.views import oidc_views
from testflinger.owasp import OWASPLogger
from testflinger.providers import ISODatetimeProvider
from testflinger.views import views

try:
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration
except ImportError:
    pass

VANILLA_FRAMEWORK_VERSION = "4.52.0"  # renovate: vanilla-framework-latest


def create_flask_app(config=None, secrets_store=None):
    """Create the flask app."""
    tf_app = APIFlask(__name__, title="Testflinger API", version="1.0.0")

    # Globally disable strict slashes
    tf_app.url_map.strict_slashes = False
    tf_app.url_map.converters.update(log_type=LogTypeConverter)
    if config:
        tf_app.config.from_object(config)

    # Set up OWASP logger on the app
    logger = OWASPLogger(logger=logging.getLogger(f"testflinger.{id(tf_app)}"))
    logger.setLevel(logging.INFO)
    # Only add explicit handler in production (not testing)
    if not tf_app.config.get("TESTING"):
        logger.addHandler(logging.StreamHandler())
    tf_app.owasp_logger = logger

    tf_app.config["PROPAGATE_EXCEPTIONS"] = True

    # Return datetime objects as RFC3339/ISO8601 strings
    tf_app.json = ISODatetimeProvider(tf_app)

    if tf_app.config.get("TESTING") is not True:
        setup_mongodb(tf_app)

    tf_app.secrets_store = secrets_store

    # Attempt to register app with OIDC
    tf_app.oauth = app_register_oidc(tf_app=tf_app)

    sentry_dsn = tf_app.config.get("SENTRY_DSN")
    if sentry_dsn and "sentry_sdk" in globals():
        sentry_sdk.init(  # pylint: disable=abstract-class-instantiated
            dsn=sentry_dsn, integrations=[FlaskIntegration()]
        )

    metrics.group_by = "endpoint"
    metrics.init_app(tf_app)

    @tf_app.errorhandler(NotFound)
    def handle_404(exc):
        tf_app.owasp_logger.error("[404] Not found: %s", request.url)
        return f"Not found: {exc}\n", 404

    @tf_app.errorhandler(ConnectionFailure)
    def handle_timeout(exc):
        tf_app.owasp_logger.exception("pymongo connection failure: %s", exc)
        return "Server Connection Failure", 500

    @tf_app.errorhandler(Exception)
    def unhandled_exception(exc):
        tf_app.owasp_logger.exception("Unhandled Exception: %s", exc)
        return f"Unhandled Exception: {exc}\n", 500

    @tf_app.context_processor
    def inject_oidc_status():
        return {"oidc_enabled": tf_app.oauth is not None}

    @tf_app.context_processor
    def inject_vanilla_framework_version():
        return {"vanilla_framework_version": VANILLA_FRAMEWORK_VERSION}

    # Tell Flask it's behind a proxy so it can properly handle redirects
    # This middleware should only be used if the application is actually
    # behind such a proxy, and should be configured with the number of
    # proxies that are chained in front of it. Not all proxies set all
    # the headers.
    if os.environ.get("ENABLE_PROXYFIX", "false").lower() == "true":
        tf_app.wsgi_app = ProxyFix(
            tf_app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
        )

    tf_app.register_blueprint(views)
    tf_app.register_blueprint(v1, url_prefix="/v1")
    if tf_app.oauth:
        tf_app.register_blueprint(oidc_views, url_prefix="/auth")
        tf_app.register_blueprint(oidc_api, url_prefix="/oidc")

    return tf_app
