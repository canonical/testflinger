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

import os

from testflinger import v1
from testflinger import errors
from flask import(
    Flask,
    jsonify,
)


class DefaultConfig(object):
    AMQP_URI = 'amqp://guest:guest@localhost:5672//'
    PROPAGATE_EXCEPTIONS = True


def create_flask_app():
    app = Flask(__name__)

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

    @app.errorhandler(errors.CustomHttpException)
    def handle_custom_exception(error):
        response = jsonify(error.to_dict())
        response.status_code = error._http_status
        return response

    return app

app = create_flask_app()
