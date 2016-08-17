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
import redis
import os
import uuid

from flask import(
    jsonify,
    request,
)

import testflinger


def home():
    """Identify ourselves"""
    return 'Testflinger Server'


def job_post():
    """Add a job to the queue"""
    data = request.get_json()
    try:
        job_queue = data.get('job_queue')
    except AttributeError:
        # Set job_queue to None so we take the failure path below
        job_queue = None
    if not job_queue:
        return "Invalid data or no job_queue specified\n", 400
    job_id = str(uuid.uuid4())
    data['job_id'] = job_id
    submit_job(job_queue, json.dumps(data))
    return jsonify(job_id=job_id)


def job_get():
    """Request a job to run from supported queues"""
    queue_list = request.args.getlist('queue')
    if not queue_list:
        return "No queue(s) specified in request", 400
    job = get_job(queue_list)
    if job:
        return job
    else:
        return "", 204


def result_post(job_id):
    """Post a result for a specified job_id

    :param job_id:
        UUID as a string for the job
    """
    if not check_valid_uuid(job_id):
        return 'Invalid job id\n', 400
    data = request.get_json()
    result_file = os.path.join(testflinger.app.config.get('DATA_PATH'), job_id)
    with open(result_file, 'w') as results:
        results.write(json.dumps(data))
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
    result_file = os.path.join(testflinger.app.config.get('DATA_PATH'), job_id)
    if not os.path.exists(result_file):
        return "", 204
    with open(result_file) as results:
        data = results.read()
    return data


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
    redis_host = testflinger.app.config.get('REDIS_HOST')
    redis_port = testflinger.app.config.get('REDIS_PORT')
    client = redis.Redis(host=redis_host, port=redis_port)
    client.lpush(job_queue, data)


def get_job(queue_list):
    redis_host = testflinger.app.config.get('REDIS_HOST')
    redis_port = testflinger.app.config.get('REDIS_PORT')
    client = redis.Redis(host=redis_host, port=redis_port)
    # The queue name and the job are returned, but we don't need the queue now
    try:
        _, job = client.brpop(queue_list, timeout=1)
    except TypeError:
        return None
    return job
