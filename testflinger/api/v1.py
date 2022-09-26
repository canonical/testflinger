# Copyright (C) 2022 Canonical
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
from datetime import datetime
from gridfs import GridFS
from gridfs.errors import NoFile

import pkg_resources
from flask import current_app, jsonify, request, send_file
from werkzeug.exceptions import BadRequest
from prometheus_client import Counter


jobs_metric = Counter("jobs", "Number of jobs", ["queue"])
reservations_metric = Counter("reservations", "Number of reservations")


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

    try:
        job = job_builder(data)
    except ValueError:
        return "Invalid job_id specified\n", 400

    jobs_metric.labels(queue=job_queue).inc()
    if "reserve_data" in data:
        reservations_metric.inc()

    # CAUTION! If you ever move this line, you may need to pass data as a copy
    # because it will get modified by submit_job and other things it calls
    current_app.db.jobs.insert_one(job)
    return jsonify(job_id=job.get("job_id"))


def job_builder(data):
    """Build a job from a dictionary of data"""
    job = {
        "created_at": datetime.utcnow(),
        "result_data": {
            "job_state": "waiting",
        },
    }
    # If the job_id is provided, keep it as long as the uuid is good.
    # This is for job resubmission
    job_id = data.pop("job_id", None)
    if job_id and isinstance(job_id, str):
        # This job already came with a job_id, so it was resubmitted
        if not check_valid_uuid(job_id):
            raise ValueError
    else:
        # This is a new job, so generate a new job_id
        job_id = str(uuid.uuid4())

    job["job_id"] = job_id
    job["job_data"] = data
    return job


def job_get():
    """Request a job to run from supported queues"""
    queue_list = request.args.getlist("queue")
    if not queue_list:
        return "No queue(s) specified in request", 400
    job = get_job(queue_list)
    if job:
        return jsonify(job)
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
    response = current_app.db.jobs.find_one(
        {"job_id": job_id}, projection={"job_data": True, "_id": False}
    )
    if not response:
        return "", 204
    job_data = response.get("job_data")
    job_data["job_id"] = job_id
    return jsonify(job_data), 200


def result_post(job_id):
    """Post a result for a specified job_id

    :param job_id:
        UUID as a string for the job
    """
    if not check_valid_uuid(job_id):
        return "Invalid job id\n", 400
    try:
        result_data = request.get_json()
    except BadRequest:
        return "Invalid result data\n", 400

    # First, we need to prepend "result_data" to each key in the result_data
    for key in list(result_data):
        result_data[f"result_data.{key}"] = result_data.pop(key)

    current_app.db.jobs.update_one({"job_id": job_id}, {"$set": result_data})
    return "OK"


def result_get(job_id):
    """Return results for a specified job_id

    :param job_id:
        UUID as a string for the job
    """
    if not check_valid_uuid(job_id):
        return "Invalid job id\n", 400
    response = current_app.db.jobs.find_one(
        {"job_id": job_id}, {"result_data": True, "_id": False}
    )

    if not response or not (results := response.get("result_data")):
        return "", 204
    results = response.get("result_data")
    return jsonify(results)


def artifacts_post(job_id):
    """Post artifact bundle for a specified job_id

    :param job_id:
        UUID as a string for the job
    """
    if not check_valid_uuid(job_id):
        return "Invalid job id\n", 400
    file = request.files["file"]
    filename = f"{job_id}.artifact"
    # Normally we would use flask-pymongo save_file but it doesn't seem to
    # work nicely for me with mongomock
    storage = GridFS(current_app.db)
    file_id = storage.put(file, filename=filename)

    # Add a timestamp to the chunks - do this so we can set a TTL for them
    timestamp = current_app.db.fs.files.find_one({"_id": file_id})[
        "uploadDate"
    ]
    current_app.db.fs.chunks.update_many(
        {"files_id": file_id}, {"$set": {"uploadDate": timestamp}}
    )
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
    filename = f"{job_id}.artifact"
    # Normally we would use flask-pymongo send_file but it doesn't seem to
    # work nicely for me with mongomock
    storage = GridFS(current_app.db)
    try:
        file = storage.get_last_version(filename=filename)
    except NoFile:
        return "", 204
    return send_file(file, download_name="artifact.tar.gz")


def output_get(job_id):
    """Get latest output for a specified job ID

    :param job_id:
        UUID as a string for the job
    :return:
        Output lines
    """
    if not check_valid_uuid(job_id):
        return "Invalid job id\n", 400
    response = current_app.db.output.find_one_and_delete(
        {"job_id": job_id}, {"_id": False}
    )
    output = response.get("output", []) if response else None
    if output:
        return "\n".join(output)
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
    data = request.get_data().decode("utf-8")
    timestamp = datetime.utcnow()
    current_app.db.output.update_one(
        {"job_id": job_id},
        {"$set": {"updated_at": timestamp}, "$push": {"output": data}},
        upsert=True,
    )
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
    all_queues = current_app.db.queues.find(
        {}, projection={"_id": False, "name": True, "description": True}
    )
    queue_dict = {}
    # Create a dict of queues and descriptions
    for queue in all_queues:
        queue_dict[queue.get("name")] = queue.get("description", "")
    return jsonify(queue_dict)


def queues_post():
    """Tell testflinger the queue names that are being serviced

    Some agents may want to advertise some of the queues they listen on so that
    the user can check which queues are valid to use.
    """
    queue_dict = request.get_json()
    for queue, description in queue_dict.items():
        current_app.db.queues.update_one(
            {"name": queue},
            {"$set": {"description": description}},
            upsert=True,
        )
    return "OK"


def images_get(queue):
    """Get a list of known images for a given queue"""
    queue_data = current_app.db.queues.find_one(
        {"name": queue}, {"_id": False, "images": True}
    )
    # It's ok for this to just return an empty result if there are none found
    return jsonify(queue_data.get("images", {}))


def images_post():
    """Tell testflinger about known images for a specified queue
    images will be stored in a list of key/value pairs as part of the queues
    collection. That list will contain image_name:provision_data mappings, ex:
    [
        "name":"some_queue",
        ...
        "images": [
            {"core22": "http://cdimage.ubuntu.com/.../core-22.tar.gz"},
            {"jammy": "http://cdimage.ubuntu.com/.../ubuntu-22.04.tar.gz"}
        ],
        "other_queue": [
            ...
        ]
    ]
    """
    image_dict = request.get_json()
    # We need to delete and recreate the images in case some were removed
    for queue, image_data in image_dict.items():
        current_app.db.queues.update_one(
            {"name": queue},
            {"$set": {"images": image_data}},
            upsert=True,
        )
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


def get_job(queue_list):
    """Get the next job in the queue"""
    # The queue name and the job are returned, but we don't need the queue now
    try:
        response = current_app.db.jobs.find_one_and_update(
            {
                "result_data.job_state": "waiting",
                "job_data.job_queue": {"$in": queue_list},
            },
            {"$set": {"result_data.job_state": "running"}},
            projection={"job_id": True, "job_data": True, "_id": False},
        )
    except TypeError:
        return None
    if not response:
        return None
    # Flatten the job_data and include the job_id
    job = response.get("job_data")
    job["job_id"] = response.get("job_id")
    return job


def job_position_get(job_id):
    """Return the position of the specified jobid in the queue"""
    response, http_code = job_get_id(job_id)
    if http_code != 200:
        return response, http_code
    job_data = response.json
    if not job_data:
        return "Job not found or already started\n", 410
    try:
        queue = job_data.get("job_queue")
    except (AttributeError, TypeError):
        return "Invalid json returned for id: {}\n".format(job_id), 400
    # Get all jobs with job_queue=queue and return only the _id
    jobs = current_app.db.jobs.find(
        {"job_data.job_queue": queue}, {"job_id": 1}
    )
    # Create a dict mapping job_id (as a string) to the position in the queue
    jobs_id_position = {job.get("job_id"): pos for pos, job in enumerate(jobs)}
    if job_id in jobs_id_position:
        return str(jobs_id_position[job_id])
    return "Job not found or already started\n", 410


def cancel_job(job_id):
    """Cancellation for a specified job ID

    :param job_id:
        UUID as a string for the job
    """
    # Set the job status to cancelled
    response = current_app.db.jobs.update_one(
        {
            "job_id": job_id,
            "result_data.job_state": {"$nin": ["cancelled", "completed"]},
        },
        {"$set": {"result_data.job_state": "cancelled"}},
    )
    if response.modified_count == 0:
        return "The job is already completed or cancelled", 400
    return "OK"
