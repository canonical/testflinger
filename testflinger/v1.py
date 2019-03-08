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
import os
import uuid

from flask import (
    jsonify,
    request,
    send_file
)

import testflinger


def home():
    """Identify ourselves"""
    return testflinger._get_version()


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
    # Prepend tf_queue on job queues for easier ID
    job_queue = "tf_queue_" + job_queue
    # If the job_id is provided, keep it as long as the uuid is good.
    # This is for job resubmission
    job_id = data.get('job_id')
    if not job_id:
        job_id = str(uuid.uuid4())
        data['job_id'] = job_id
    elif not check_valid_uuid(job_id):
        return "Invalid job_id specified\n", 400
    submit_job(job_queue, json.dumps(data))
    job_file = os.path.join(
        testflinger.app.config.get('DATA_PATH'), job_id + '.json')
    with open(job_file, 'w') as jobfile:
        jobfile.write(json.dumps(data))
    # Add a result file with job_state=waiting
    result_file = os.path.join(testflinger.app.config.get('DATA_PATH'), job_id)
    if os.path.exists(result_file):
        with open(result_file) as results:
            data = json.load(results)
            data['job_state'] = 'resubmitted'
    else:
        data = {'job_state': 'waiting'}
    with open(result_file, 'w') as results:
        results.write(json.dumps(data))
    return jsonify(job_id=job_id)


def job_get():
    """Request a job to run from supported queues"""
    queue_list = request.args.getlist('queue')
    if not queue_list:
        return "No queue(s) specified in request", 400
    # Temporarily look for jobs with and without tf_queue_
    job = get_job(queue_list)
    if job:
        return job
    else:
        queue_list = ['tf_queue_' + x for x in queue_list]
        job = get_job(queue_list)
        if job:
            return job
        else:
            return "", 204


def job_get_id(job_id):
    """Request the json job definition for a specified job, even if it has
       already run

    :param job_id:
        UUID as a string for the job
    :return:
        JSON data for the job

    >>> job_get_id('foo')
    ('Invalid job id\\n', 400)
    """

    if not check_valid_uuid(job_id):
        return 'Invalid job id\n', 400
    job_file = os.path.join(
        testflinger.app.config.get('DATA_PATH'), job_id + '.json')
    if not os.path.exists(job_file):
        return "", 204
    with open(job_file) as jobfile:
        data = jobfile.read()
    return data


def result_post(job_id):
    """Post a result for a specified job_id

    :param job_id:
        UUID as a string for the job
    """
    if not check_valid_uuid(job_id):
        return 'Invalid job id\n', 400
    result_file = os.path.join(testflinger.app.config.get('DATA_PATH'), job_id)
    if os.path.exists(result_file):
        with open(result_file) as results:
            data = json.load(results)
    else:
        data = {}
    new_data = request.get_json()
    data.update(new_data)
    with open(result_file, 'w') as results:
        results.write(json.dumps(data))
    return "OK"


def result_get(job_id):
    """Return results for a specified job_id

    :param job_id:
        UUID as a string for the job
    """
    if not check_valid_uuid(job_id):
        return 'Invalid job id\n', 400
    result_file = os.path.join(testflinger.app.config.get('DATA_PATH'), job_id)
    if not os.path.exists(result_file):
        return "", 204
    with open(result_file) as results:
        data = results.read()
    return data


def artifacts_post(job_id):
    """Post artifact bundle for a specified job_id

    :param job_id:
        UUID as a string for the job
    """
    if not check_valid_uuid(job_id):
        return 'Invalid job id\n', 400
    file = request.files['file']
    filename = '{}.artifact'.format(job_id)
    file.save(os.path.join(testflinger.app.config.get('DATA_PATH'), filename))
    return "OK"


def artifacts_get(job_id):
    """Return artifact bundle for a specified job_id

    :param job_id:
        UUID as a string for the job
    :return:
        send_file stream of artifact tarball to download
    """
    if not check_valid_uuid(job_id):
        return 'Invalid job id\n', 400
    artifact_file = os.path.join(
        testflinger.app.config.get('DATA_PATH'), '{}.artifact'.format(job_id))
    if not os.path.exists(artifact_file):
        return "", 204
    return send_file(artifact_file)


def output_get(job_id):
    """Get latest output for a specified job ID

    :param job_id:
        UUID as a string for the job
    :return:
        Output lines
    """
    if not check_valid_uuid(job_id):
        return 'Invalid job id\n', 400
    output_key = "stream_{}".format(job_id)
    pipe = testflinger.app.redis.pipeline()
    pipe.lrange(output_key, 0, -1)
    pipe.delete(output_key)
    output = pipe.execute()
    if output[0]:
        return '\n'.join([x.decode() for x in output[0]])
    else:
        return '', 204


def output_post(job_id):
    """Post output for a specified job ID

    :param job_id:
        UUID as a string for the job
    :param data:
        A list containing the lines of output to post

    >>> output_post('foo')
    ('Invalid job id\\n', 400)
    """
    if not check_valid_uuid(job_id):
        return 'Invalid job id\n', 400
    data = request.get_data()
    output_key = "stream_{}".format(job_id)
    testflinger.app.redis.rpush(output_key, data)
    # If the data doesn't get read with 4 hours of the last update, expire it
    testflinger.app.redis.expire(output_key, 14400)
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
    except Exception:
        return False
    return True


def submit_job(job_queue, data):
    """Submit a job to the specified queue for processing

    :param job_queue:
        Name of the queue to use as a string
    :param data:
        JSON data to pass along containing details about the test job
    """
    testflinger.app.redis.lpush(job_queue, data)


def get_job(queue_list):
    # The queue name and the job are returned, but we don't need the queue now
    try:
        _, job = testflinger.app.redis.brpop(queue_list, timeout=1)
    except TypeError:
        return None
    return job


def job_position_get(job_id):
    job_data = json.loads(job_get_id(job_id))
    queue = "tf_queue_" + job_data.get('job_queue')
    for position, x in enumerate(
            reversed(testflinger.app.redis.lrange(queue, 0, -1))):
        if json.loads(
                x.decode('utf-8', errors='ignore')).get('job_id') == job_id:
            return str(position)
