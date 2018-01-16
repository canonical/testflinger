# Copyright (C) 2016 Canonical
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

import logging
import pkg_resources
import os

from testflinger import v1
from flask import Flask


def _get_version():
    try:
        version = pkg_resources.get_distribution("testflinger").version
    except pkg_resources.DistributionNotFound:
        version = "devel"
    return 'Testflinger Server v{}'.format(version)


class DefaultConfig(object):
    REDIS_HOST = 'localhost'
    REDIS_PORT = '6379'
    DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'data')
    PROPAGATE_EXCEPTIONS = True


def create_flask_app():
    app = Flask(__name__)

    if not app.debug:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        app.logger.addHandler(stream_handler)

    app.config.from_object(DefaultConfig)
    # Additional config can be specified with env var TESTFLINGER_CONFIG
    # Otherwise load it from testflinger.conf in the testflinger dir
    config_file = os.environ.get('TESTFLINGER_CONFIG', 'testflinger.conf')
    app.config.from_pyfile(config_file, silent=True)
    if not os.path.exists(app.config['DATA_PATH']):
        os.makedirs(app.config['DATA_PATH'])

    app.add_url_rule('/', 'home', v1.home)
    app.add_url_rule('/v1/job', 'job_post', v1.job_post, methods=['POST'])
    app.add_url_rule('/v1/job', 'job_get', v1.job_get, methods=['GET'])
    app.add_url_rule('/v1/job/<job_id>', 'job_get_id', v1.job_get_id,
                     methods=['GET'])
    app.add_url_rule('/v1/result/<job_id>', 'result_post', v1.result_post,
                     methods=['POST'])
    app.add_url_rule('/v1/result/<job_id>', 'result_get', v1.result_get,
                     methods=['GET'])
    app.add_url_rule('/v1/result/<job_id>/artifact', 'artifacts_post',
                     v1.artifacts_post, methods=['POST'])
    app.add_url_rule('/v1/result/<job_id>/artifact', 'artifacts_get',
                     v1.artifacts_get, methods=['GET'])
    app.add_url_rule('/v1/result/<job_id>/output', 'output_post',
                     v1.output_post, methods=['POST'])
    app.add_url_rule('/v1/result/<job_id>/output', 'output_get',
                     v1.output_get, methods=['GET'])

    @app.errorhandler(Exception)
    def unhandled_exception(e):
        app.logger.exception('Unhandled Exception: %s', (e))
        return 'Unhandled Exception: {}\n'.format(e), 500

    return app


app = create_flask_app()
