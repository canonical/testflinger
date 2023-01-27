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
"""
This sets up the Testflinger web application
"""

import logging
import os

from flask import Flask, request
from flask.logging import create_logger
from werkzeug.exceptions import NotFound
from pymongo.errors import ConnectionFailure

from src.database import mongo
from src.api import v1
from src.views import views

# Constants for TTL indexes
DEFAULT_EXPIRATION = 60 * 60 * 24 * 7  # 7 days
OUTPUT_EXPIRATION = 60 * 60 * 4  # 4 hours

try:
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration
except ImportError:
    pass


def create_flask_app(config=None):
    """Create the flask app"""
    tf_app = Flask(__name__)
    if config:
        tf_app.config.from_object(config)
    tf_log = create_logger(tf_app)

    if not tf_app.debug:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        tf_log.addHandler(stream_handler)

    tf_app.config["PROPAGATE_EXCEPTIONS"] = True

    if tf_app.config.get("TESTING") is not True:
        setup_mongodb(tf_app)

    sentry_dsn = tf_app.config.get("SENTRY_DSN")
    if sentry_dsn and "sentry_sdk" in globals():
        sentry_sdk.init(  # pylint: disable=abstract-class-instantiated
            dsn=sentry_dsn, integrations=[FlaskIntegration()]
        )

    tf_app.add_url_rule("/", "home", v1.home)
    tf_app.add_url_rule("/v1/job", "job_post", v1.job_post, methods=["POST"])
    tf_app.add_url_rule("/v1/job", "job_get", v1.job_get, methods=["GET"])
    tf_app.add_url_rule(
        "/v1/job/<job_id>", "job_get_id", v1.job_get_id, methods=["GET"]
    )
    tf_app.add_url_rule(
        "/v1/job/<job_id>/position",
        "job_position_get",
        v1.job_position_get,
        methods=["GET"],
    )
    tf_app.add_url_rule(
        "/v1/result/<job_id>", "result_post", v1.result_post, methods=["POST"]
    )
    tf_app.add_url_rule(
        "/v1/result/<job_id>", "result_get", v1.result_get, methods=["GET"]
    )
    tf_app.add_url_rule(
        "/v1/result/<job_id>/artifact",
        "artifacts_post",
        v1.artifacts_post,
        methods=["POST"],
    )
    tf_app.add_url_rule(
        "/v1/result/<job_id>/artifact",
        "artifacts_get",
        v1.artifacts_get,
        methods=["GET"],
    )
    tf_app.add_url_rule(
        "/v1/result/<job_id>/output",
        "output_post",
        v1.output_post,
        methods=["POST"],
    )
    tf_app.add_url_rule(
        "/v1/result/<job_id>/output",
        "output_get",
        v1.output_get,
        methods=["GET"],
    )
    tf_app.add_url_rule(
        "/v1/job/<job_id>/action",
        "action_post",
        v1.action_post,
        methods=["POST"],
    )
    tf_app.add_url_rule(
        "/v1/agents/queues", "queues_get", v1.queues_get, methods=["GET"]
    )
    tf_app.add_url_rule(
        "/v1/agents/queues", "queues_post", v1.queues_post, methods=["POST"]
    )
    tf_app.add_url_rule(
        "/v1/agents/images/<queue>",
        "images_get",
        v1.images_get,
        methods=["GET"],
    )
    tf_app.add_url_rule(
        "/v1/agents/images", "images_post", v1.images_post, methods=["POST"]
    )

    tf_app.add_url_rule(
        "/v1/agents/data/<agent_name>",
        "agents_post",
        v1.agents_post,
        methods=["POST"],
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

    return tf_app


def setup_mongodb(application):
    """
    Setup mongodb connection if we have valid config data
    Otherwise leave it empty, which means we are probably running unit tests
    """

    mongo_user = os.environ.get("MONGODB_USERNAME")
    mongo_pass = os.environ.get("MONGODB_PASSWORD")
    mongo_db = os.environ.get("MONGODB_DATABASE")
    mongo_host = os.environ.get("MONGODB_HOST")
    mongo_port = os.environ.get("MONGODB_PORT", "27017")
    mongo_uri = os.environ.get("MONGODB_URI")

    if not mongo_uri:
        if not (mongo_host and mongo_db):
            raise SystemExit("No MongoDB URI configured!")
        mongo_creds = (
            f"{mongo_user}:{mongo_pass}@" if mongo_user and mongo_pass else ""
        )
        mongo_uri = (
            f"mongodb://{mongo_creds}{mongo_host}:{mongo_port}/{mongo_db}"
        )

    mongo.init_app(
        application,
        uri=mongo_uri,
        uuidRepresentation="standard",
        serverSelectionTimeoutMS=2000,
        socketTimeoutMS=10000,
    )

    # Initialize collections and indices in case they don't exist already
    # Automatically expire jobs after 7 days if nothing runs them
    mongo.db.jobs.create_index(
        "created_at", expireAfterSeconds=DEFAULT_EXPIRATION
    )
    # Remove output 4 hours after the last entry if nothing polls for it
    mongo.db.output.create_index(
        "updated_at", expireAfterSeconds=OUTPUT_EXPIRATION
    )
    # Remove artifacts after 7 days
    mongo.db.fs.chunks.create_index(
        "uploadDate", expireAfterSeconds=DEFAULT_EXPIRATION
    )
    mongo.db.fs.files.create_index(
        "uploadDate", expireAfterSeconds=DEFAULT_EXPIRATION
    )
