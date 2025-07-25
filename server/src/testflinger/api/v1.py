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
"""Testflinger v1 API."""

import importlib.metadata
import os
import uuid
from datetime import datetime, timezone
from http import HTTPStatus

import requests
from apiflask import APIBlueprint, abort
from flask import g, jsonify, request, send_file
from prometheus_client import Counter
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from werkzeug.exceptions import BadRequest

from testflinger import database
from testflinger.api import auth, schemas
from testflinger.api.auth import authenticate, require_role
from testflinger.enums import ServerRoles

jobs_metric = Counter(
    "jobs", "Number of jobs", ["queue"], namespace="testflinger"
)
reservations_metric = Counter(
    "reservations",
    "Number of reservations",
    ["queue"],
    namespace="testflinger",
)


v1 = APIBlueprint("v1", __name__)


@v1.get("/")
def home():
    """Identify ourselves."""
    return get_version()


def get_version():
    """Return the Testflinger version."""
    try:
        version = importlib.metadata.version("testflinger")
    except importlib.metadata.PackageNotFoundError:
        version = "devel"
    return f"Testflinger Server v{version}"


@v1.post("/job")
@authenticate
@v1.input(schemas.Job, location="json")
@v1.output(schemas.JobId)
def job_post(json_data: dict):
    """Add a job to the queue."""
    try:
        job_queue = json_data.get("job_queue")
    except (AttributeError, BadRequest):
        # Set job_queue to None so we take the failure path below
        job_queue = ""
    if not job_queue:
        abort(422, message="Invalid data or no job_queue specified")
    try:
        job = job_builder(json_data)
    except ValueError:
        abort(400, message="Invalid job_id specified")

    jobs_metric.labels(queue=job_queue).inc()
    if "reserve_data" in json_data:
        reservations_metric.labels(queue=job_queue).inc()

    # CAUTION! If you ever move this line, you may need to pass data as a copy
    # because it will get modified by submit_job and other things it calls
    database.add_job(job)
    return jsonify(job_id=job.get("job_id"))


def has_attachments(data: dict) -> bool:
    """Predicate if the job described by `data` involves attachments."""
    return any(
        nested_field == "attachments"
        for field, nested_dict in data.items()
        if field.endswith("_data") and isinstance(nested_dict, dict)
        for nested_field in nested_dict
    )


def job_builder(data: dict):
    """Build a job from a dictionary of data."""
    job = {
        "created_at": datetime.now(timezone.utc),
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

    # side effect: modify the job dict
    if has_attachments(data):
        data["attachments_status"] = "waiting"

    priority_level = data.get("job_priority", 0)
    auth.check_permissions(
        g.permissions,
        data,
    )
    job["job_priority"] = priority_level

    job["job_id"] = job_id
    job["job_data"] = data
    return job


@v1.get("/job")
@v1.output(schemas.Job)
@v1.doc(responses=schemas.job_empty)
def job_get():
    """Request a job to run from supported queues."""
    queue_list = request.args.getlist("queue")
    if not queue_list:
        return "No queue(s) specified in request", 400
    job = database.pop_job(queue_list=queue_list)
    if job:
        job["started_at"] = datetime.now(timezone.utc)
        return jsonify(job)
    return {}, 204


@v1.get("/job/<job_id>")
@v1.output(schemas.Job)
def job_get_id(job_id):
    """Request the json job definition for a specified job, even if it has
       already run.

    :param job_id:
        UUID as a string for the job
    :return:
        JSON data for the job or error string and http error
    """
    if not check_valid_uuid(job_id):
        abort(400, message="Invalid job_id specified")
    response = database.mongo.db.jobs.find_one(
        {"job_id": job_id}, projection={"job_data": True, "_id": False}
    )
    if not response:
        return {}, 204
    job_data = response.get("job_data")
    job_data["job_id"] = job_id
    return job_data


@v1.get("/job/<job_id>/attachments")
def attachment_get(job_id):
    """Return the attachments bundle for a specified job_id.

    :param job_id:
        UUID as a string for the job
    :return:
        send_file stream of attachment tarball to download
    """
    if not check_valid_uuid(job_id):
        return "Invalid job id\n", 400
    try:
        file = database.retrieve_file(filename=f"{job_id}.attachments")
    except FileNotFoundError:
        return "", 204
    return send_file(file, mimetype="application/gzip")


@v1.post("/job/<job_id>/attachments")
def attachments_post(job_id):
    """Post attachment bundle for a specified job_id.

    :param job_id:
        UUID as a string for the job
    """
    if not check_valid_uuid(job_id):
        return "Invalid job id\n", 400
    try:
        attachments_status = database.get_attachments_status(job_id)
    except ValueError:
        return f"Job {job_id} is not valid\n", 422
    if attachments_status is None:
        return f"Job {job_id} not awaiting attachments\n", 422
    if attachments_status == "complete":
        # attachments already submitted: successful, could be due to a retry
        return "OK", 200

    # save attachments archive in the database
    database.save_file(
        data=request.files["file"],
        filename=f"{job_id}.attachments",
    )

    # now the job can be processed
    database.attachments_received(job_id)
    return "OK", 200


@v1.get("/job/search")
@v1.input(schemas.JobSearchRequest, location="query")
@v1.output(schemas.JobSearchResponse)
def search_jobs(query_data):
    """Search for jobs by tags."""
    tags = query_data.get("tags")
    match = request.args.get("match", "any")
    states = request.args.getlist("state")

    query = {}
    if tags and match == "all":
        query["job_data.tags"] = {"$all": tags}
    elif tags and match == "any":
        query["job_data.tags"] = {"$in": tags}

    if "active" in states:
        query["result_data.job_state"] = {
            "$nin": ["cancelled", "complete", "completed"]
        }
    elif states:
        query["result_data.job_state"] = {"$in": states}

    pipeline = [
        {"$match": query},
        {
            "$project": {
                "job_id": True,
                "created_at": True,
                "job_state": "$result_data.job_state",
                "_id": False,
            },
        },
    ]

    jobs = database.mongo.db.jobs.aggregate(pipeline)

    return jsonify(list(jobs))


@v1.post("/result/<job_id>")
@v1.input(schemas.Result, location="json")
def result_post(job_id, json_data):
    """Post a result for a specified job_id.

    :param job_id:
        UUID as a string for the job
    """
    if not check_valid_uuid(job_id):
        abort(400, message="Invalid job_id specified")

    # fail if input payload is larger than the BSON size limit
    # https://www.mongodb.com/docs/manual/reference/limits/
    content_length = request.content_length
    if content_length and content_length >= 16 * 1024 * 1024:
        abort(413, message="Payload too large")

    # First, we need to prepend "result_data" to each key in the result_data
    for key in list(json_data):
        json_data[f"result_data.{key}"] = json_data.pop(key)

    database.mongo.db.jobs.update_one({"job_id": job_id}, {"$set": json_data})
    return "OK"


@v1.get("/result/<job_id>")
@v1.output(schemas.Result)
def result_get(job_id):
    """Return results for a specified job_id.

    :param job_id:
        UUID as a string for the job
    """
    if not check_valid_uuid(job_id):
        abort(400, message="Invalid job_id specified")
    response = database.mongo.db.jobs.find_one(
        {"job_id": job_id}, {"result_data": True, "_id": False}
    )

    if not response or not (results := response.get("result_data")):
        return "", 204
    results = response.get("result_data")
    return results


@v1.post("/result/<job_id>/artifact")
def artifacts_post(job_id):
    """Post artifact bundle for a specified job_id.

    :param job_id:
        UUID as a string for the job
    """
    if not check_valid_uuid(job_id):
        return "Invalid job id\n", 400
    database.save_file(
        data=request.files["file"],
        filename=f"{job_id}.artifact",
    )
    return "OK"


@v1.get("/result/<job_id>/artifact")
def artifacts_get(job_id):
    """Return artifact bundle for a specified job_id.

    :param job_id:
        UUID as a string for the job
    :return:
        send_file stream of artifact tarball to download
    """
    if not check_valid_uuid(job_id):
        return "Invalid job id\n", 400
    try:
        file = database.retrieve_file(filename=f"{job_id}.artifact")
    except FileNotFoundError:
        return "", 204
    return send_file(file, download_name="artifact.tar.gz")


@v1.get("/result/<job_id>/output")
def output_get(job_id):
    """Get latest output for a specified job ID.

    :param job_id:
        UUID as a string for the job
    :return:
        Output lines
    """
    if not check_valid_uuid(job_id):
        return "Invalid job id\n", 400
    response = database.mongo.db.output.find_one_and_delete(
        {"job_id": job_id}, {"_id": False}
    )
    output = response.get("output", []) if response else None
    if output:
        return "\n".join(output)
    return "", 204


@v1.post("/result/<job_id>/output")
def output_post(job_id):
    """Post output for a specified job ID.

    :param job_id:
        UUID as a string for the job
    :param data:
        A string containing the latest lines of output to post
    """
    if not check_valid_uuid(job_id):
        abort(400, message="Invalid job_id specified")
    data = request.get_data().decode("utf-8")
    timestamp = datetime.now(timezone.utc)
    database.mongo.db.output.update_one(
        {"job_id": job_id},
        {"$set": {"updated_at": timestamp}, "$push": {"output": data}},
        upsert=True,
    )
    return "OK"


@v1.get("/result/<job_id>/serial_output")
def serial_output_get(job_id):
    """Get latest serial output for a specified job ID.

    :param job_id:
        UUID as a string for the job
    :return:
        Output lines
    """
    if not check_valid_uuid(job_id):
        return "Invalid job id\n", 400
    response = database.mongo.db.serial_output.find_one_and_delete(
        {"job_id": job_id}, {"_id": False}
    )
    output = response.get("serial_output", []) if response else None
    if output:
        return "\n".join(output)
    return "", 204


@v1.post("/result/<job_id>/serial_output")
def serial_output_post(job_id):
    """Post output for a specified job ID.

    :param job_id:
        UUID as a string for the job
    :param data:
        A string containing the latest lines of output to post
    """
    if not check_valid_uuid(job_id):
        abort(400, message="Invalid job_id specified")
    data = request.get_data().decode("utf-8")
    timestamp = datetime.now(timezone.utc)
    database.mongo.db.serial_output.update_one(
        {"job_id": job_id},
        {"$set": {"updated_at": timestamp}, "$push": {"serial_output": data}},
        upsert=True,
    )
    return "OK"


@v1.post("/job/<job_id>/action")
@v1.input(schemas.ActionIn, location="json")
def action_post(job_id, json_data):
    """Take action on the job status for a specified job ID.

    :param job_id:
        UUID as a string for the job
    """
    if not check_valid_uuid(job_id):
        return "Invalid job id\n", 400
    action = json_data["action"]
    supported_actions = {
        "cancel": cancel_job,
    }
    # Validation of actions happens in schemas.py:ActionIn
    return supported_actions[action](job_id)


@v1.get("/agents/queues")
@v1.doc(responses=schemas.queues_out)
def queues_get():
    """Get all advertised queues from this server.

    Returns a dict of queue names and descriptions, ex:
    {
        "some_queue": "A queue for testing",
        "other_queue": "A queue for something else"
    }
    """
    all_queues = database.mongo.db.queues.find(
        {}, projection={"_id": False, "name": True, "description": True}
    )
    queue_dict = {}
    # Create a dict of queues and descriptions
    for queue in all_queues:
        queue_dict[queue.get("name")] = queue.get("description", "")
    return jsonify(queue_dict)


@v1.post("/agents/queues")
def queues_post():
    """Tell testflinger the queue names that are being serviced.

    Some agents may want to advertise some of the queues they listen on so that
    the user can check which queues are valid to use.
    """
    queue_dict = request.get_json()
    timestamp = datetime.now(timezone.utc)
    for queue, description in queue_dict.items():
        database.mongo.db.queues.update_one(
            {"name": queue},
            {"$set": {"description": description, "updated_at": timestamp}},
            upsert=True,
        )
    return "OK"


@v1.get("/agents/images/<queue>")
@v1.doc(responses=schemas.images_out)
def images_get(queue):
    """Get a dict of known images for a given queue."""
    queue_data = database.mongo.db.queues.find_one(
        {"name": queue}, {"_id": False, "images": True}
    )
    if not queue_data:
        return jsonify({})
    # It's ok for this to just return an empty result if there are none found
    return jsonify(queue_data.get("images", {}))


@v1.post("/agents/images")
def images_post():
    """Tell testflinger about known images for a specified queue
    images will be stored in a dict of key/value pairs as part of the queues
    collection. That dict will contain image_name:provision_data mappings, ex:
    {
        "some_queue": {
            "core22": "http://cdimage.ubuntu.com/.../core-22.tar.gz",
            "jammy": "http://cdimage.ubuntu.com/.../ubuntu-22.04.tar.gz"
        },
        "other_queue": {
            ...
        }
    }.
    """
    image_dict = request.get_json()
    # We need to delete and recreate the images in case some were removed
    for queue, image_data in image_dict.items():
        database.mongo.db.queues.update_one(
            {"name": queue},
            {"$set": {"images": image_data}},
            upsert=True,
        )
    return "OK"


@v1.get("/agents/data")
@v1.output(schemas.AgentOut(many=True))
def agents_get_all():
    """Get all agent data."""
    agents = database.get_agents()
    restricted_queues = database.get_restricted_queues()
    restricted_queues_owners = database.get_restricted_queues_owners()

    for agent in agents:
        agent["restricted_to"] = {
            queue: restricted_queues_owners[queue]
            for queue in agent.get("queues", [])
            if queue in restricted_queues
            and restricted_queues_owners.get(queue)
        }

    return jsonify(agents)


@v1.get("/agents/data/<agent_name>")
@v1.output(schemas.AgentOut)
def agents_get_one(agent_name):
    """Get the information from a specified agent.

    :param agent_name:
        String with the name of the agent to retrieve information from.
    :return:
        JSON data with the specified agent information.
    """
    agent_data = database.get_agent_info(agent_name)

    if not agent_data:
        return {}, HTTPStatus.NOT_FOUND

    restricted_queues = database.get_restricted_queues()
    restricted_queues_owners = database.get_restricted_queues_owners()

    agent_data["restricted_to"] = {
        queue: restricted_queues_owners[queue]
        for queue in agent_data.get("queues", [])
        if queue in restricted_queues and restricted_queues_owners.get(queue)
    }

    return jsonify(agent_data)


@v1.post("/agents/data/<agent_name>")
@v1.input(schemas.AgentIn, location="json")
def agents_post(agent_name, json_data):
    """Post information about the agent to the server.

    The json sent to this endpoint may contain data such as the following:
    {
        "state": string, # State the device is in
        "queues": array[string], # Queues the device is listening on
        "location": string, # Location of the device
        "job_id": string, # Job ID the device is running, if any
        "log": array[string], # push and keep only the last 100 lines
    }
    """
    json_data["name"] = agent_name
    json_data["updated_at"] = datetime.now(timezone.utc)
    # extract log from data so we can push it instead of setting it
    log = json_data.pop("log", [])

    database.mongo.db.agents.update_one(
        {"name": agent_name},
        {"$set": json_data, "$push": {"log": {"$each": log, "$slice": -100}}},
        upsert=True,
    )
    return "OK"


@v1.post("/agents/provision_logs/<agent_name>")
@v1.input(schemas.ProvisionLogsIn, location="json")
def agents_provision_logs_post(agent_name, json_data):
    """Post provision logs for the agent to the server."""
    agent_record = {}

    # timestamp this agent record and provision log entry
    timestamp = datetime.now(timezone.utc)
    agent_record["updated_at"] = json_data["timestamp"] = timestamp

    update_operation = {
        "$set": json_data,
        "$push": {
            "provision_log": {"$each": [json_data], "$slice": -100},
        },
    }
    database.mongo.db.provision_logs.update_one(
        {"name": agent_name},
        update_operation,
        upsert=True,
    )
    agent = database.mongo.db.agents.find_one(
        {"name": agent_name},
        {"provision_streak_type": 1, "provision_streak_count": 1},
    )
    if not agent:
        return "Agent not found\n", 404
    previous_provision_streak_type = agent.get("provision_streak_type", "")
    previous_provision_streak_count = agent.get("provision_streak_count", 0)

    agent["provision_streak_type"] = (
        "fail" if json_data["exit_code"] != 0 else "pass"
    )
    if agent["provision_streak_type"] == previous_provision_streak_type:
        agent["provision_streak_count"] = previous_provision_streak_count + 1
    else:
        agent["provision_streak_count"] = 1
    database.mongo.db.agents.update_one({"name": agent_name}, {"$set": agent})
    return "OK"


@v1.post("/job/<job_id>/events")
@v1.input(schemas.StatusUpdate, location="json")
def agents_status_post(job_id, json_data):
    """Post status updates from the agent to the server to be forwarded
    to TestObserver.

    The json sent to this endpoint may contain data such as the following:
    {
        "agent_id": "<string>",
        "job_queue": "<string>",
        "job_status_webhook": "<URL as string>",
        "events": [
        {
            "event_name": "<string enum of events>",
            "timestamp": "<datetime>",
            "detail": "<string>"
        },
        ...
        ]
    }

    """
    _ = job_id
    request_json = json_data
    webhook_url = request_json.pop("job_status_webhook")
    try:
        s = requests.Session()
        s.mount(
            "",
            HTTPAdapter(
                max_retries=Retry(
                    total=3,
                    allowed_methods=frozenset(["PUT"]),
                    backoff_factor=1,
                )
            ),
        )
        response = s.put(webhook_url, json=request_json, timeout=3)
        return response.text, response.status_code
    except requests.exceptions.Timeout:
        return "Webhook Timeout", 504


def check_valid_uuid(job_id):
    """Check that the specified job_id is a valid UUID only.

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


@v1.get("/job/<job_id>/position")
def job_position_get(job_id):
    """Return the position of the specified jobid in the queue."""
    job_data, status = job_get_id(job_id)
    if status == 204:
        return "Job not found or already started\n", 410
    if status != 200:
        return job_data
    try:
        queue = job_data.json.get("job_queue")
    except (AttributeError, TypeError):
        return f"Invalid json returned for id: {job_id}\n", 400
    # Get all jobs with job_queue=queue and return only the _id
    jobs = database.mongo.db.jobs.find(
        {"job_data.job_queue": queue, "result_data.job_state": "waiting"},
        {"job_id": 1},
        sort=[("job_priority", -1)],
    )
    # Create a dict mapping job_id (as a string) to the position in the queue
    jobs_id_position = {job.get("job_id"): pos for pos, job in enumerate(jobs)}
    if job_id in jobs_id_position:
        return str(jobs_id_position[job_id])
    return "Job not found or already started\n", 410


def cancel_job(job_id):
    """Cancel a specified job ID.

    :param job_id:
        UUID as a string for the job
    """
    # Set the job status to cancelled
    response = database.mongo.db.jobs.update_one(
        {
            "job_id": job_id,
            "result_data.job_state": {
                "$nin": ["cancelled", "complete", "completed"]
            },
        },
        {"$set": {"result_data.job_state": "cancelled"}},
    )
    if response.modified_count == 0:
        return "The job is already completed or cancelled", 400
    return "OK"


@v1.get("/queues/wait_times")
def queue_wait_time_percentiles_get():
    """Get wait time metrics - optionally take a list of queues."""
    queues = request.args.getlist("queue")
    wait_times = database.get_queue_wait_times(queues)
    queue_percentile_data = {}
    for queue in wait_times:
        queue_percentile_data[queue["name"]] = database.calculate_percentiles(
            queue["wait_times"]
        )
    return queue_percentile_data


@v1.get("/queues/<queue_name>/agents")
@v1.output(schemas.AgentOut(many=True))
def get_agents_on_queue(queue_name):
    """Get the list of all data for agents listening to a specified queue."""
    if not database.queue_exists(queue_name):
        return [], HTTPStatus.NOT_FOUND

    agents = database.get_agents_on_queue(queue_name)
    if not agents:
        return [], HTTPStatus.NO_CONTENT
    return agents


@v1.get("/queues/<queue_name>/jobs")
def get_jobs_by_queue(queue_name):
    """Get the jobs in a specified queue along with its state.

    :param queue_name
        String with the queue name where to perform the query.
    :return:
        JSON data with the jobs allocated to the specified queue.
    """
    jobs = database.get_jobs_on_queue(queue_name)

    if not jobs:
        return {}, HTTPStatus.NO_CONTENT

    try:
        jobs_in_queue = [
            {
                "job_id": job["job_id"],
                "created_at": job["created_at"],
                "job_state": job["result_data"]["job_state"],
                "job_queue": job["job_data"]["job_queue"],
            }
            for job in jobs
        ]
    except KeyError:
        abort(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            message="Unable to retrieve information about specified queue.",
        )

    return jsonify(jobs_in_queue)


@v1.post("/oauth2/token")
def retrieve_token():
    """
    Get JWT with priority and queue permissions.

    Before being encrypted, the JWT can contain fields like:
    {
        exp: <Expiration DateTime of Token>,
        iat: <Issuance DateTime of Token>,
        sub: <Subject Field of Token>,
        permissions: {
            max_priority: <Queue to Priority Level Dict>,
            allowed_queues: <List of Allowed Restricted Queues>,
            max_reservation_time: <Queue to Max Reservation Time Dict>,
        }
    }
    """
    auth_header = request.authorization
    if auth_header is None:
        return "No authorization header specified", 401
    client_id = auth_header["username"]
    client_key = auth_header["password"]
    if client_id is None or client_key is None:
        return (
            "Client id and key must be specified in authorization header",
            401,
        )

    allowed_resources = auth.validate_client_key_pair(client_id, client_key)
    if allowed_resources is None:
        return "Invalid client id or client key", 401
    secret_key = os.environ.get("JWT_SIGNING_KEY")
    token = auth.generate_token(allowed_resources, secret_key)
    return token


@v1.get("/restricted-queues")
@authenticate
@require_role(ServerRoles.ADMIN, ServerRoles.MANAGER, ServerRoles.CONTRIBUTOR)
@v1.output(schemas.RestrictedQueueOut(many=True))
def get_all_restricted_queues() -> list[dict]:
    """List all agent's restricted queues and its owners."""
    restricted_queues = database.get_restricted_queues()
    restricted_queues_owners = database.get_restricted_queues_owners()

    response = []
    for queue in restricted_queues:
        owners = restricted_queues_owners.get(queue, [])
        response.append(
            {
                "queue": queue,
                "owners": owners,
            }
        )

    return jsonify(response)


@v1.get("/restricted-queues/<queue_name>")
@authenticate
@require_role(ServerRoles.ADMIN, ServerRoles.MANAGER, ServerRoles.CONTRIBUTOR)
@v1.output(schemas.RestrictedQueueOut)
def get_restricted_queue(queue_name: str) -> dict:
    """Get restricted queues for a specific agent."""
    if not database.check_queue_restricted(queue_name):
        abort(HTTPStatus.NOT_FOUND, "Error: Restricted queue not found.")

    restricted_queues_owners = database.get_restricted_queues_owners()
    owners = restricted_queues_owners.get(queue_name, [])

    return jsonify(
        {
            "queue": queue_name,
            "owners": owners,
        }
    )


@v1.post("/restricted-queues/<queue_name>")
@authenticate
@require_role(ServerRoles.ADMIN, ServerRoles.MANAGER)
@v1.input(schemas.RestrictedQueueIn, location="json")
def add_restricted_queue(queue_name: str, json_data: dict) -> dict:
    """Add an owner to the specific restricted queue."""
    client_id = json_data.get("client_id", "")

    if not client_id:
        abort(HTTPStatus.BAD_REQUEST, "Error: Missing client ID.")

    if not database.queue_exists(queue_name):
        abort(
            HTTPStatus.NOT_FOUND,
            "Error: No agent is associated with the specified queue.",
        )

    database.add_restricted_queue(queue_name, client_id)

    return "OK"


@v1.delete("/restricted-queues/<queue_name>")
@authenticate
@require_role(ServerRoles.ADMIN, ServerRoles.MANAGER)
@v1.input(schemas.RestrictedQueueIn, location="json")
def delete_restricted_queue(queue_name: str, json_data: dict) -> dict:
    """Delete an owner from the specific restricted queue."""
    if not database.check_queue_restricted(queue_name):
        abort(HTTPStatus.NOT_FOUND, "Error: Restricted queue not found.")

    client_id = json_data.get("client_id", "")
    if not client_id:
        abort(HTTPStatus.BAD_REQUEST, "Error: Missing client ID.")

    database.delete_restricted_queue(queue_name, client_id)

    return "OK"
