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

import json
import kombu
import uuid

from flask import(
    jsonify,
    request,
)

import testflinger


def home():
    """Identify ourselves"""
    return 'Testflinger Server'


def add_job():
    """Add a job to the queue"""
    data = request.get_json()
    try:
        job_queue = data.get('job_queue')
    except AttributeError:
        # Set job_queue to None so we take the failure path below
        job_queue = None
    if not job_queue:
        return "Invalid data or no job_queue specified\n", 400
    submit_job(job_queue, json.dumps(data))
    return jsonify(job_id=uuid.uuid1())


def result_post(job_id):
    """Post a result for a specified job_id

    :param job_id:
        UUID as a string for the job
    """
    if not check_valid_uuid(job_id):
        return 'Invalid job id\n', 400
    return "OK"


def result_get(job_id):
    """Return results for a specified job_id

    :param job_id:
        UUID as a string for the job
    :return:
        json data of results for the specified id
    """
    if not check_valid_uuid(job_id):
        return 'Invalid job id\n', 400
    return "OK"


def check_valid_uuid(job_id):
    """Check that the specified job_id is a valid UUID only

    :param job_id:
        UUID as a string for the job
    :return:
        True if job_id is valid, False if not
    """

    try:
        uuid.UUID(job_id)
    except:
        return False
    return True


def submit_job(job_queue, data):
    """Submit a job to the specified queue for processing

    :param job_queue:
        Name of the queue to use as a string
    :param data:
        JSON data to pass along containing details about the test job
    """
    amqp_uri = testflinger.app.config.get('AMQP_URI')
    with kombu.Connection(amqp_uri) as conn:
        with conn.SimpleQueue(job_queue) as queue:
            queue.put(data)
