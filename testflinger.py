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
from dataclasses import dataclass
import pkg_resources
import redis
from flask import Flask
from flask.logging import create_logger
from api import v1

try:
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration
except ImportError:
    pass


def get_version():
    """Return the Testflinger version"""
    try:
        version = pkg_resources.get_distribution("testflinger").version
    except pkg_resources.DistributionNotFound:
        version = "devel"
    return 'Testflinger Server v{}'.format(version)


@dataclass(frozen=True)
class DefaultConfig():
    """
    Default config object for Testflinger
    """
    REDIS_HOST = 'localhost'
    REDIS_PORT = '6379'
    DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'data')
    PROPAGATE_EXCEPTIONS = True


def create_flask_app():
    """Create the flask app"""
    tf_app = Flask(__name__)
    tf_log = create_logger(tf_app)

    if not tf_app.debug:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        tf_log.addHandler(stream_handler)

    tf_app.config.from_object(DefaultConfig)
    # Additional config can be specified with env var TESTFLINGER_CONFIG
    # Otherwise load it from testflinger.conf in the testflinger dir
    config_file = os.environ.get('TESTFLINGER_CONFIG', 'testflinger.conf')
    tf_app.config.from_pyfile(config_file, silent=True)
    if not os.path.exists(tf_app.config['DATA_PATH']):
        os.makedirs(tf_app.config['DATA_PATH'])

    tf_app.redis = redis.StrictRedis(
        host=tf_app.config['REDIS_HOST'], port=tf_app.config['REDIS_PORT'])

    sentry_dsn = tf_app.config.get("SENTRY_DSN")
    if sentry_dsn and 'sentry_sdk' in globals():
        sentry_sdk.init(dsn=sentry_dsn, integrations=[FlaskIntegration()])

    tf_app.add_url_rule('/', 'home', v1.home)
    tf_app.add_url_rule('/v1/job', 'job_post', v1.job_post, methods=['POST'])
    tf_app.add_url_rule('/v1/job', 'job_get', v1.job_get, methods=['GET'])
    tf_app.add_url_rule('/v1/job/<job_id>', 'job_get_id', v1.job_get_id,
                        methods=['GET'])
    tf_app.add_url_rule('/v1/job/<job_id>/position', 'job_position_get',
                        v1.job_position_get, methods=['GET'])
    tf_app.add_url_rule('/v1/result/<job_id>', 'result_post', v1.result_post,
                        methods=['POST'])
    tf_app.add_url_rule('/v1/result/<job_id>', 'result_get', v1.result_get,
                        methods=['GET'])
    tf_app.add_url_rule('/v1/result/<job_id>/artifact', 'artifacts_post',
                        v1.artifacts_post, methods=['POST'])
    tf_app.add_url_rule('/v1/result/<job_id>/artifact', 'artifacts_get',
                        v1.artifacts_get, methods=['GET'])
    tf_app.add_url_rule('/v1/result/<job_id>/output', 'output_post',
                        v1.output_post, methods=['POST'])
    tf_app.add_url_rule('/v1/result/<job_id>/output', 'output_get',
                        v1.output_get, methods=['GET'])
    tf_app.add_url_rule('/v1/agents/queues', 'queues_get',
                        v1.queues_get, methods=['GET'])
    tf_app.add_url_rule('/v1/agents/queues', 'queues_post',
                        v1.queues_post, methods=['POST'])
    tf_app.add_url_rule('/v1/agents/images/<queue>', 'images_get',
                        v1.images_get, methods=['GET'])
    tf_app.add_url_rule('/v1/agents/images', 'images_post',
                        v1.images_post, methods=['POST'])

    @tf_app.errorhandler(Exception)
    def unhandled_exception(exc):
        tf_log.exception('Unhandled Exception: %s', (exc))
        return 'Unhandled Exception: {}\n'.format(exc), 500

    return tf_app


app = create_flask_app()
