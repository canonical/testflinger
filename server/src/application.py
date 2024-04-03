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
"""
This sets up the Testflinger web application
"""

import logging

from flask import request
from flask.logging import create_logger
from werkzeug.exceptions import NotFound
from pymongo.errors import ConnectionFailure
from apiflask import APIFlask

from src.database import setup_mongodb
from src.api.v1 import v1
from src.providers import ISODatetimeProvider
from src.views import views

try:
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration
except ImportError:
    pass


def create_flask_app(config=None):
    """Create the flask app"""
    tf_app = APIFlask(__name__)
    if config:
        tf_app.config.from_object(config)
    tf_log = create_logger(tf_app)

    if not tf_app.debug:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        tf_log.addHandler(stream_handler)

    tf_app.config["PROPAGATE_EXCEPTIONS"] = True

    # Return datetime objects as RFC3339/ISO8601 strings
    tf_app.json = ISODatetimeProvider(tf_app)

    if tf_app.config.get("TESTING") is not True:
        setup_mongodb(tf_app)

    sentry_dsn = tf_app.config.get("SENTRY_DSN")
    if sentry_dsn and "sentry_sdk" in globals():
        sentry_sdk.init(  # pylint: disable=abstract-class-instantiated
            dsn=sentry_dsn, integrations=[FlaskIntegration()]
        )

    @tf_app.errorhandler(NotFound)
    def handle_404(exc):
        tf_log.error("[404] Not found: %s", request.url)
        return "Not found: {}\n".format(exc), 404

    @tf_app.errorhandler(ConnectionFailure)
    def handle_timeout(exc):
        tf_log.exception("pymongo connection failure: %s", exc)
        return "Server Connection Failure", 500

    @tf_app.errorhandler(Exception)
    def unhandled_exception(exc):
        tf_log.exception("Unhandled Exception: %s", (exc))
        return "Unhandled Exception: {}\n".format(exc), 500

    tf_app.register_blueprint(views)
    tf_app.register_blueprint(v1, url_prefix="/v1")

    return tf_app
