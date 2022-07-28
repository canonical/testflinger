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
Testflinger v1 API
"""

import json
import uuid

import pkg_resources
from flask import current_app, jsonify, request, send_file
from werkzeug.exceptions import BadRequest


def home():
    """Identify ourselves"""
    return get_version()


def get_version():
    """Return the Testflinger version"""
    try:
        version = pkg_resources.get_distribution("testflinger").version
    except pkg_resources.DistributionNotFound:
        version = "devel"
    return "Testflinger Server v{}".format(version)


def job_post():
    """Add a job to the queue"""
    try:
        data = request.get_json()
        job_queue = data.get("job_queue")
    except (AttributeError, BadRequest):
        # Set job_queue to None so we take the failure path below
        job_queue = ""
    if not job_queue:
        return "Invalid data or no job_queue specified\n", 400
    # Prepend tf_queue on job queues for easier ID
    job_queue = "tf_queue_" + str(job_queue)
    # If the job_id is provided, keep it as long as the uuid is good.
    # This is for job resubmission
    job_id = data.get("job_id")
    if not job_id:
        job_id = str(uuid.uuid4())
        data["job_id"] = job_id
    elif not check_valid_uuid(job_id):
        return "Invalid job_id specified\n", 400
    submit_job(job_queue, json.dumps(data))
    job_file = current_app.config.get("DATA_PATH") / (job_id + ".json")
    with open(job_file, "w", encoding="utf-8", errors="ignore") as jobfile:
        jobfile.write(json.dumps(data))
    # Add a result file with job_state=waiting
    result_file = current_app.config.get("DATA_PATH") / job_id
    if result_file.exists():
        with open(
            result_file, "r", encoding="utf-8", errors="ignore"
        ) as results:
            data = json.load(results)
            data["job_state"] = "resubmitted"
    else:
        data = {"job_state": "waiting"}
    with open(result_file, "w", encoding="utf-8", errors="ignore") as results:
        results.write(json.dumps(data))
    return jsonify(job_id=job_id)


def job_get():
    """Request a job to run from supported queues"""
    queue_list = request.args.getlist("queue")
    if not queue_list:
        return "No queue(s) specified in request", 400
    queue_list = ["tf_queue_" + x for x in queue_list]
    job = get_job(queue_list)
    if job:
        return job
    return "", 204


def job_get_id(job_id):
    """Request the json job definition for a specified job, even if it has
       already run

    :param job_id:
        UUID as a string for the job
    :return:
        JSON data for the job or error string and http error

    >>> job_get_id('foo')
    ('Invalid job id\\n', 400)
    """

    if not check_valid_uuid(job_id):
        return "Invalid job id\n", 400
    job_file = current_app.config.get("DATA_PATH") / (job_id + ".json")
    if not job_file.exists():
        return "", 204
    with open(job_file, "r", encoding="utf-8", errors="ignore") as jobfile:
        data = jobfile.read()
    return data, 200


def result_post(job_id):
    """Post a result for a specified job_id

    :param job_id:
        UUID as a string for the job
    """
    if not check_valid_uuid(job_id):
        return "Invalid job id\n", 400
    result_file = current_app.config.get("DATA_PATH") / job_id
    if result_file.exists():
        try:
            with open(
                result_file, "r", encoding="utf-8", errors="ignore"
            ) as results:
                data = json.load(results)
        except json.decoder.JSONDecodeError:
            # If for any reason it's empty or has bad data - set to empty dict
            data = {}
    else:
        data = {}
    try:
        new_data = request.get_json()
    except BadRequest:
        return "Invalid result data\n", 400
    data.update(new_data)
    with open(result_file, "w", encoding="utf-8", errors="ignore") as results:
        results.write(json.dumps(data))
    return "OK"


def result_get(job_id):
    """Return results for a specified job_id

    :param job_id:
        UUID as a string for the job
    """
    if not check_valid_uuid(job_id):
        return "Invalid job id\n", 400
    result_file = current_app.config.get("DATA_PATH") / job_id
    if not result_file.exists():
        return "", 204
    with open(result_file, "r", encoding="utf-8", errors="ignore") as results:
        data = results.read()
    return data


def artifacts_post(job_id):
    """Post artifact bundle for a specified job_id

    :param job_id:
        UUID as a string for the job
    """
    if not check_valid_uuid(job_id):
        return "Invalid job id\n", 400
    file = request.files["file"]
    filename = "{}.artifact".format(job_id)
    file.save(current_app.config.get("DATA_PATH") / filename)
    return "OK"


def artifacts_get(job_id):
    """Return artifact bundle for a specified job_id

    :param job_id:
        UUID as a string for the job
    :return:
        send_file stream of artifact tarball to download
    """
    if not check_valid_uuid(job_id):
        return "Invalid job id\n", 400
    artifact_file = current_app.config.get("DATA_PATH") / "{}.artifact".format(
        job_id
    )
    if not artifact_file.exists():
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
        return "Invalid job id\n", 400
    output_key = "stream_{}".format(job_id)
    pipe = current_app.redis.pipeline()
    pipe.lrange(output_key, 0, -1)
    pipe.delete(output_key)
    output = pipe.execute()
    if output[0]:
        return "\n".join([x.decode() for x in output[0]])
    return "", 204


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
        return "Invalid job id\n", 400
    data = request.get_data()
    output_key = "stream_{}".format(job_id)
    current_app.redis.rpush(output_key, data)
    # If the data doesn't get read with 4 hours of the last update, expire it
    current_app.redis.expire(output_key, 14400)
    return "OK"


def action_post(job_id):
    """Take action on the job status for a specified job ID

    :param job_id:
        UUID as a string for the job
    """
    if not check_valid_uuid(job_id):
        return "Invalid job id\n", 400
    data = json.loads(request.get_data())
    action = data["action"]
    actions = {
        "cancel": cancel_job,
    }
    if action in actions:
        return actions[action](job_id)
    return "Invalid action\n", 400


def queues_get():
    """Get a current list of all advertised queues from this server"""
    redis_list = current_app.redis.keys("tf:qlist:*")
    queue_dict = {}
    # Create a dict of queues and descriptions
    for queue_name in redis_list:
        # strip tf:qlist: from the key to get the queue name
        queue_dict[queue_name[9:].decode()] = current_app.redis.get(
            queue_name
        ).decode()
    return jsonify(queue_dict)


def queues_post():
    """Tell testflinger the queue names that are being serviced

    Some agents may want to advertise some of the queues they listen on so that
    the user can check which queues are valid to use.
    """
    queue_dict = request.get_json()
    pipe = current_app.redis.pipeline()
    for queue in queue_dict:
        queue_name = "tf:qlist:" + queue
        queue_description = queue_dict[queue]
        pipe.set(queue_name, queue_description, ex=300)
    pipe.execute()
    return "OK"


def images_get(queue):
    """Get a list of known images for a given queue"""
    images = current_app.redis.hgetall("tf:images:" + queue)
    images = {k.decode(): v.decode() for k, v in images.items()}
    return jsonify(images)


def images_post():
    """Tell testflinger about known images for a specified queue"""
    image_dict = request.get_json()
    pipe = current_app.redis.pipeline()
    # We need to delete and recreate the hash in case images were removed
    for queue, images in image_dict.items():
        pipe.delete("tf:images:" + queue)
        pipe.hmset("tf:images:" + queue, images)
    pipe.execute()
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
    except ValueError:
        return False
    return True


def submit_job(job_queue, data):
    """Submit a job to the specified queue for processing

    :param job_queue:
        Name of the queue to use as a string
    :param data:
        JSON data to pass along containing details about the test job
    """
    pipe = current_app.redis.pipeline()
    pipe.lpush(job_queue, data)
    # Delete the queue after 1 week if nothing is looking at it
    pipe.expire(job_queue, 604800)
    pipe.execute()


def remove_job(job_queue, job_id):
    """Remove a job from the specified queue if there's just job ID in DB

    :param job_queue:
        Name of the queue to use as a string
    :param data:
        JSON data to pass along containing details about the test job
    """
    database = current_app.redis
    database.lrem(job_queue, 1, job_id)


def get_job(queue_list):
    """Get the next job in the queue"""
    # The queue name and the job are returned, but we don't need the queue now
    try:
        _, job = current_app.redis.brpop(queue_list, timeout=1)
    except TypeError:
        return None
    return job


def job_position_get(job_id):
    """Return the position of the specified jobid in the queue"""
    data, http_code = job_get_id(job_id)
    if http_code != 200:
        return data, http_code
    try:
        job_data = json.loads(data)
    except (json.JSONDecodeError, TypeError):
        return "Invalid json returned for id: {}\n".format(job_id), 400
    queue = "tf_queue_" + job_data.get("job_queue")
    for position, job in enumerate(
        reversed(current_app.redis.lrange(queue, 0, -1))
    ):
        if (
            json.loads(job.decode("utf-8", errors="ignore")).get("job_id")
            == job_id
        ):
            return str(position)
    return "Job not found or already started\n", 410


def cancel_job(job_id):
    """Cancellation for a specified job ID

    :param job_id:
        UUID as a string for the job
    """
    result_file = current_app.config.get("DATA_PATH") / job_id
    if not result_file.exists():
        return "Job is not found and cannot be cancelled\n", 400
    try:
        with open(
            result_file, "r", encoding="utf-8", errors="ignore"
        ) as results:
            data = json.load(results)
    except json.decoder.JSONDecodeError:
        # If for any reason it's empty or has bad data
        data = {"job_state": "bad_data"}
    if data["job_state"] in ["complete", "cancelled"]:
        return "The job is already completed or cancelled", 400
    job_file = current_app.config.get("DATA_PATH") / (job_id + ".json")
    with open(job_file, "r", encoding="utf-8", errors="ignore") as jobfile:
        job_data = json.load(jobfile)
        output_key = "tf_queue_{}".format(job_data["job_queue"])
    remove_job(output_key, job_id)
    # Set the job status to cancelled
    with open(result_file, "w", encoding="utf-8", errors="ignore") as results:
        results.write(json.dumps({"job_state": "cancelled"}))
    return "OK"
