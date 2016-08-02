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
import os

from testflinger import v1
from flask import Flask


class DefaultConfig(object):
    AMQP_URI = 'amqp://guest:guest@localhost:5672//'
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

    app.add_url_rule('/', 'home', v1.home)
    app.add_url_rule('/v1/job', 'add_job', v1.add_job, methods=['POST'])
    app.add_url_rule('/v1/result/<job_id>', 'result_post', v1.result_post,
                     methods=['POST'])
    app.add_url_rule('/v1/result/<job_id>', 'result_get', v1.result_get,
                     methods=['GET'])

    @app.errorhandler(Exception)
    def unhandled_exception(e):
        app.logger.exception('Unhandled Exception: %s', (e))
        return 'Unhandled Exception: {}\n'.format(e), 500

    return app

app = create_flask_app()
