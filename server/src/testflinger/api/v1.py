# Copyright (C) 2022-2025 Canonical
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
from apiflask import APIBlueprint, abort, security
from flask import current_app, g, jsonify, request, send_file
from marshmallow import ValidationError
from prometheus_client import Counter
from requests.adapters import HTTPAdapter
from testflinger_common.enums import LogType, TestPhase
from urllib3.util.retry import Retry
from werkzeug.exceptions import BadRequest
from werkzeug.routing import BaseConverter

from testflinger import database
from testflinger.api import auth, schemas
from testflinger.api.auth import authenticate, require_role
from testflinger.enums import ServerRoles
from testflinger.logs import LogFragment, MongoLogHandler
from testflinger.secrets.exceptions import (
    AccessError,
    StoreError,
    UnexpectedError,
)

TESTFLINGER_ADMIN_ID = "testflinger-admin"

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
@v1.input(
    schemas.Job,
    location="json",
    example={
        "job_queue": "myqueue",
        "name": "Example Test Job",
        "tags": ["test", "sample"],
        "provision_data": {"url": "<url>"},
        "test_data": {"test_cmds": "lsb_release -a"},
    },
)
@v1.output(
    schemas.JobId,
    status_code=200,
    description="(OK) Returns the job_id (UUID) of the newly created job",
    example={"job_id": "550e8400-1234-1234-1234-446655440000"},
)
@v1.doc(
    responses={
        422: {
            "description": (
                "(Unprocessable Content) The submitted job contains "
                "references to secrets that are inaccessible"
            )
        }
    }
)
def job_post(json_data: dict):
    """Create a test job request and place it on the specified queue.

    Most parameters passed in the data section of this API will be specific
    to the type of agent receiving them. The `job_queue` parameter is used
    to designate the queue used, but all others will be passed along to
    the agent.
    """
    try:
        job_queue = json_data.get("job_queue")
    except (AttributeError, BadRequest):
        # Set job_queue to None so we take the failure path below
        job_queue = ""
    if not job_queue:
        abort(422, message="Invalid data or no job_queue specified")

    validate_secrets(json_data)

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


def validate_secrets(data: dict):
    """Validate that all secret paths in the job exist in the secrets store."""
    try:
        secrets = data["test_data"]["secrets"]
    except KeyError:
        return

    # a secrets store must be set up
    if current_app.secrets_store is None:
        abort(HTTPStatus.UNPROCESSABLE_ENTITY, message="No secrets store")

    # the client must be authenticated in order to access their own secrets
    if (client_id := g.client_id) is None:
        abort(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            message="Missing client ID (user not authenticated)",
        )

    # check that all secrets paths correspond to stored secrets
    # (i.e. a job containing secrets cannot be submitted unless all its secrets
    # are accessible.)
    inaccessible_paths = []
    for secret_path in secrets.values():
        try:
            current_app.secrets_store.read(client_id, secret_path)
        except (AccessError, StoreError, UnexpectedError):
            inaccessible_paths.append(secret_path)
    if inaccessible_paths:
        abort(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            message=(
                "Inaccessible secret paths: "
                + ", ".join(sorted(inaccessible_paths))
            ),
        )

    # side-effect: store client ID with job (so that secrets are retrievable)
    data["client_id"] = client_id


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
@v1.input(
    schema=schemas.JobGetQuery,
    location="query",
    arg_name="queue",
    example=["foo", "bar"],
)
@v1.output(
    schemas.Job,
    status_code=200,
    description="(OK) JSON job data that was submitted by the requester",
)
@v1.doc(
    responses={
        204: {
            "description": (
                "(No Content) No jobs available in the specified queues"
            )
        },
        400: {
            "description": (
                "(Bad request) No queue is specified in the request"
            )
        },
    }
)
def job_get():
    """Get a test job from the specified queue(s).

    When an agent wants to request a job for processing, it can make this
    request along with a list of one or more queues that it is configured
    to process. The server will only return one job.

    Note:
        Any secrets that are referenced in the job are "resolved" when the
        job is retrieved by an agent through this endpoint. Any secrets that
        are inaccessible at the time of retrieval will be resolved to the
        empty string.
    """
    queue_list = request.args.getlist("queue")
    if not queue_list:
        return "No queue(s) specified in request", HTTPStatus.BAD_REQUEST
    job = database.pop_job(queue_list=queue_list)
    if not job:
        return jsonify({}), HTTPStatus.NO_CONTENT
    if (secrets := retrieve_secrets(job)) is not None:
        job["test_data"]["secrets"] = secrets
    job["started_at"] = datetime.now(timezone.utc)
    return jsonify(job)


def retrieve_secrets(data: dict) -> dict | None:
    """
    Retrieve all secrets from the secrets store.

    Any secrets that are not accessible at the time of retrieval will be
    resolved to the empty string, instead of the retrieval failing.
    It is the responsibility of the consumer of the secrets to account for
    this possibility. This is a design decision and it mirrors how undefined
    secrets are handled in other platforms such as GitHub.
    """
    try:
        secrets = data["test_data"]["secrets"]
    except KeyError:
        return None

    # a secrets store must be set up and the client_id must have been specified
    if (
        current_app.secrets_store is None
        or (client_id := data.get("client_id")) is None
    ):
        return dict.fromkeys(secrets, "")

    result = {}
    for identifier, secret_path in secrets.items():
        try:
            secret_value = current_app.secrets_store.read(
                client_id, secret_path
            )
        except (AccessError, StoreError, UnexpectedError):
            secret_value = ""
        result[identifier] = secret_value
    return result


@v1.get("/job/<job_id>")
@v1.input(schema=schemas.JobId, location="path", arg_name="job_id")
@v1.output(
    schemas.Job, status_code=200, description="(OK) JSON data for the job"
)
@v1.doc(
    responses={
        400: {"description": "(Bad Request) Invalid job_id specified"},
        204: {"description": "(No Content) Job not found"},
    }
)
def job_get_id(job_id):
    """Request the json job definition for a specified job.

    Returns the job definition even if the job has already run.
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
@v1.input(schema=schemas.JobId, location="path", arg_name="job_id")
@v1.doc(
    responses={
        400: {"description": "(Bad Request) Invalid job_id specified"},
        204: {"description": "(No Content) No attachments found for this job"},
    }
)
def attachment_get(job_id):
    """Download the attachments bundle for a specified job_id.

    Returns a gzip-compressed tarball containing all files that were
    uploaded as attachments.
    """
    if not check_valid_uuid(job_id):
        return "Invalid job id\n", 400
    try:
        file = database.retrieve_file(filename=f"{job_id}.attachments")
    except FileNotFoundError:
        return "", 204
    return send_file(file, mimetype="application/gzip")


@v1.post("/job/<job_id>/attachments")
@v1.input(schema=schemas.JobId, location="path", arg_name="job_id")
@v1.input(
    schema=schemas.FileUpload,
    location="files",
)
@v1.doc(
    responses={
        400: {"description": "(Bad Request) Invalid job_id specified"},
        422: {
            "description": (
                "(Unprocessable Entity) Job not awaiting "
                "attachments or the job_id is not valid"
            )
        },
    }
)
def attachments_post(job_id):
    """Post attachment bundle for a specified job_id.

    Upload a gzip-compressed tarball containing files to be used as
    attachments for the job.
    The job must be in a state where it's awaiting attachments.
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
@v1.input(
    schemas.JobSearchRequest,
    location="query",
    example={"tags": ["foo", "bar"], "match": "all"},
)
@v1.output(
    schemas.JobSearchResponse,
    status_code=200,
    example={
        "jobs": [
            {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "job_queue": "myqueue",
            }
        ]
    },
)
def search_jobs(query_data):
    """Search for jobs by tag(s) and state(s).

    Parameters:
    - `tags` (array): List of string tags to search for
    - `match` (string): Match mode for
    - `tags` (string, "all" or "any", default: "any")
    - `state` (array): List of job states to include (or "active" to
      search all states other than cancelled and completed)
    """
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


@v1.post("/result/<job_id>/artifact")
@v1.input(schema=schemas.JobId, location="path", arg_name="job_id")
@v1.input(
    schema=schemas.FileUpload,
    location="files",
)
@v1.doc(
    responses={
        400: {"description": "(Bad Request) Invalid job_id specified"},
    }
)
def artifacts_post(job_id):
    """Upload a file artifact for the specified job_id.

    Upload a gzip-compressed tarball containing test artifacts or results
    files.
    """
    if not check_valid_uuid(job_id):
        return "Invalid job id\n", 400
    database.save_file(
        data=request.files["file"],
        filename=f"{job_id}.artifact",
    )
    return "OK"


@v1.get("/result/<job_id>/artifact")
@v1.input(schema=schemas.JobId, location="path", arg_name="job_id")
@v1.doc(
    responses={
        400: {"description": "(Bad Request) Invalid job_id specified"},
        204: {"description": "(No Content) No artifact found for this job"},
    }
)
def artifacts_get(job_id):
    """Download previously submitted artifact for the specified job_id.

    Returns a gzip-compressed tarball containing test artifacts or results
    files.
    """
    if not check_valid_uuid(job_id):
        return "Invalid job id\n", 400
    try:
        file = database.retrieve_file(filename=f"{job_id}.artifact")
    except FileNotFoundError:
        return "", 204
    return send_file(file, download_name="artifact.tar.gz")


class LogTypeConverter(BaseConverter):
    """Class to validate log type route parameter."""

    def to_python(self, value):
        """Validate log type URL parameter."""
        try:
            return LogType(value)
        except ValueError as err:
            raise ValidationError("Invalid log type") from err

    def to_url(self, obj):
        """Get string representation of log type."""
        return obj.value


@v1.get("/result/<job_id>/log/<log_type:log_type>")
@v1.input(schema=schemas.JobId, location="path", arg_name="job_id")
@v1.input(
    schema=schemas.LogTypeParam,
    location="path",
    arg_name="log_type",
    examples={
        "Get all output logs for a job": {"log_type": "output"},
    },
)
@v1.input(
    schemas.LogQueryParams,
    location="query",
    examples={
        "Get only setup phase output logs": {"phase": "setup"},
        "Get logs from fragment 5 onwards": {"start_fragment": 5},
        "Get logs after a specific timestamp": {
            "start_timestamp": "2025-10-15T10:30:00Z"
        },
    },
)
@v1.output(
    schemas.LogGet,
    status_code=200,
    description="(OK) JSON object with logs organized by phase",
    example={
        "output": {
            "setup": {
                "last_fragment_number": 5,
                "log_data": "Starting setup...\nSetup complete\n",
            },
            "provision": {
                "last_fragment_number": 12,
                "log_data": "Provisioning device...\nDevice ready\n",
            },
        }
    },
)
@v1.doc(
    responses={
        204: {
            "description": (
                "(No Content) No logs found for this job_id and log_type"
            )
        },
        400: {
            "description": (
                "(Bad Request) Invalid job_id, log_type or query "
                "parameter specified"
            )
        },
    }
)
def log_get(job_id: str, log_type: LogType):
    """Retrieve logs for the specified job_id and log type.

    This endpoint supports querying logs with optional filtering by phase,
    fragment number, or timestamp. Logs are persistent and can be
    retrieved multiple times.
    """
    args = request.args
    if not check_valid_uuid(job_id):
        abort(HTTPStatus.BAD_REQUEST, message="Invalid job id\n")
    query_schema = schemas.LogQueryParams()
    try:
        query_params = query_schema.load(args)
    except ValidationError as err:
        abort(HTTPStatus.BAD_REQUEST, message=err.messages)
    start_fragment = query_params.get("start_fragment", 0)
    start_timestamp = query_params.get("start_timestamp")
    phase = query_params.get("phase")
    log_handler = MongoLogHandler(database.mongo)

    # Return logs for all phases if unspecified
    if phase is None:
        phases = TestPhase
    else:
        phases = [TestPhase(phase)]

    return {
        log_type: {
            phase.value: log_handler.retrieve_logs(
                job_id,
                log_type,
                phase.value,
                start_fragment,
                start_timestamp,
            )
            for phase in phases
        }
    }


@v1.post("/result/<job_id>/log/<log_type:log_type>")
@v1.input(schema=schemas.JobId, location="path", arg_name="job_id")
@v1.input(
    schema=schemas.LogTypeParam,
    location="path",
    arg_name="log_type",
)
@v1.input(
    schemas.LogPost,
    location="json",
    example={
        "fragment_number": 0,
        "timestamp": "2025-10-15T10:00:00+00:00",
        "phase": "setup",
        "log_data": "Starting setup phase...",
    },
)
@v1.output(
    None, status_code=200, description="(OK) Log fragment posted successfully"
)
@v1.doc(
    responses={
        400: {
            "description": "(Bad Request) Invalid job_id or log_type specified"
        }
    }
)
def log_post(job_id: str, log_type: LogType, json_data: dict) -> str:
    """Post a log fragment for the specified job_id and log type.

    This is the new logging endpoint that agents use to stream log data
    in fragments. Each fragment includes metadata for tracking and
    querying.
    """
    if not check_valid_uuid(job_id):
        abort(HTTPStatus.BAD_REQUEST, message="Invalid job_id specified")
    log_fragment = LogFragment(
        job_id,
        log_type,
        json_data["phase"],
        json_data["fragment_number"],
        json_data["timestamp"],
        json_data["log_data"],
    )
    log_handler = MongoLogHandler(database.mongo)
    log_handler.store_log_fragment(log_fragment)
    return "OK"


@v1.post("/result/<job_id>")
@v1.input(schemas.JobId, location="path", arg_name="job_id")
@v1.input(
    schemas.ResultSchema,
    location="json",
    example={
        "status": {"setup": 0, "provision": 0, "test": 0},
        "device_info": {},
    },
)
@v1.output(
    None,
    status_code=200,
    description="(OK) Job outcome data posted successfully",
)
@v1.doc(
    responses={
        400: {"description": "(Bad Request) Invalid job_id specified"},
        413: {
            "description": (
                "(Request Entity Too Large) Payload exceeds "
                "16MB BSON size limit"
            )
        },
    }
)
def result_post(job_id: str, json_data: dict) -> str:
    """Post job outcome data for the specified job_id.

    Submit test results including exit codes for each phase, device
    information, and job state. The payload must not exceed the
    16MB BSON size limit.
    """
    if not check_valid_uuid(job_id):
        abort(HTTPStatus.BAD_REQUEST, message="Invalid job_id specified")

    # fail if input payload is larger than the BSON size limit
    # https://www.mongodb.com/docs/manual/reference/limits/
    content_length = request.content_length
    if content_length and content_length >= 16 * 1024 * 1024:
        abort(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, message="Payload too large")

    database.add_job_results(job_id, json_data)
    return "OK"


@v1.get("/result/<job_id>")
@v1.input(schemas.JobId, location="path", arg_name="job_id")
@v1.output(
    schemas.ResultGet,
    status_code=200,
    description="(OK) JSON data with flattened structure",
)
@v1.doc(
    responses={
        400: {"description": "(Bad Request) Invalid job_id specified"},
        204: {"description": "(No Content) No results found for this job_id"},
    }
)
def result_get(job_id: str):
    """Return job outcome data for the specified job_id.

    This endpoint reconstructs results from the new logging system to
    maintain backward compatibility. It combines phase status information
    with logs to provide a complete view of job results.

    Returns:
    JSON data with flattened structure including:
    - `{phase}_status`: Exit code for each phase
    - `{phase}_output`: Standard output logs for each phase
      (if available)
    - `{phase}_serial`: Serial console logs for each phase
      (if available)
    - Additional metadata fields (device_info, job_state, etc.)

    """
    if not check_valid_uuid(job_id):
        abort(HTTPStatus.BAD_REQUEST, message="Invalid job_id specified")

    response = database.get_job_results(job_id)

    if not response or not (result_data := response.get("result_data")):
        return "", HTTPStatus.NO_CONTENT

    if any(key.endswith(("_output", "_serial")) for key in result_data.keys()):
        # Legacy result format detected; return as-is
        # TODO: Remove this path after deprecating legacy endpoints
        return result_data

    # Reconstruct result format with logs and phase statuses
    log_handler = MongoLogHandler(database.mongo)
    return log_handler.format_logs_as_results(job_id, result_data)


@v1.post("/job/<job_id>/action")
@v1.input(schemas.JobId, location="path", arg_name="job_id")
@v1.input(schemas.ActionIn, location="json", example={"action": "cancel"})
@v1.output(
    None, status_code=200, description="(OK) Action executed successfully"
)
@v1.doc(
    responses={
        400: {
            "description": (
                " (Bad Request) The job is already completed or cancelled"
            )
        },
        404: {"description": "(Not Found) The job isn't found"},
        422: {
            "description": (
                "(Unprocessable Entity) The action or the argument "
                "to it could not be processed"
            )
        },
    }
)
def action_post(job_id, json_data):
    """Execute action for the specified job_id.

    Supported actions:
    - cancel: Cancel a job that hasn't been completed yet
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
@v1.input(
    schema=schemas.QueueDict,
    location="json",
    example={"myqueue": "queue 1", "myqueue2": "queue 2"},
)
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
@v1.input(schema=schemas.QueueName, location="path", arg_name="queue")
@v1.doc(responses=schemas.images_out)
def images_get(queue):
    """Get image names and provisioning data for a queue.

    Returns a dictionary mapping image names to their provisioning URLs
    or data. Returns an empty dict if the queue doesn't exist or has no
    images.
    """
    queue_data = database.mongo.db.queues.find_one(
        {"name": queue}, {"_id": False, "images": True}
    )
    if not queue_data:
        return jsonify({})
    # It's ok for this to just return an empty result if there are none found
    return jsonify(queue_data.get("images", {}))


@v1.post("/agents/images")
@v1.input(
    schema=schemas.ImagePostIn,
    location="json",
    example={
        "myqueue": {
            "core22": "http://cdimage.ubuntu.com/.../core-22.tar.gz",
            "jammy": "http://cdimage.ubuntu.com/.../ubuntu-22.04.tar.gz",
        },
        "other_queue": {"image1": "data1", "image2": "data2"},
    },
)
def images_post():
    """Tell testflinger about known images for a specified queue.

    Images will be stored in a dict of key/value pairs as part of the
    queues collection.
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
@v1.output(
    schemas.AgentOut(many=True),
    status_code=200,
    description=(
        "JSON data for all known agents, useful for external systems "
        "that need to gather this information"
    ),
)
def agents_get_all():
    """Get all agent data.

    Returns JSON data for all known agents, including their state,
    queues, location, and information about restricted queue ownership.
    Useful for external systems monitoring agents.
    """
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
@v1.input(schemas.AgentName, location="path", arg_name="agent_name")
@v1.output(
    schemas.AgentOut,
    status_code=200,
    description=(
        "JSON data for the specified agent, useful for getting "
        "information from a single agent. "
    ),
)
@v1.doc(
    responses={
        404: {"description": "(Not Found) The specified agent was not found"}
    }
)
def agents_get_one(agent_name):
    """Get the information from a specified agent.

    Returns JSON data for the specified agent, including state, queues,
    location, and restricted queue ownership information.
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
@v1.input(schemas.AgentName, location="path", arg_name="agent_name")
@v1.input(
    schemas.ProvisionLogsIn,
    location="json",
    example={
        "job_id": "00000000-0000-0000-0000-000000000000",
        "exit_code": 1,
        "detail": "foo",
    },
)
def agents_provision_logs_post(agent_name, json_data):
    """Post provision logs for the agent to the server.

    Submit provision log entries including job_id, exit_code, and detail
    information. The server maintains the last 100 provision log entries
    per agent and tracks provision success/failure streaks.
    """
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
@v1.input(schemas.JobId, location="path", arg_name="job_id")
@v1.input(
    schemas.StatusUpdate,
    location="json",
    example={
        "agent_id": "agent-00",
        "job_queue": "myqueue",
        "job_status_webhook": "http://mywebhook",
        "events": [
            {
                "event_name": "started_provisioning",
                "timestamp": "2024-05-03T19:11:33.541130+00:00",
                "detail": "my_detailed_message",
            }
        ],
    },
)
@v1.output(
    None,
    status_code=200,
    description=(
        "(OK) Text response from the webhook if the server was "
        "successfully able to post."
    ),
)
@v1.doc(
    responses={
        400: {
            "description": (
                "(Bad Request) Invalid job_id or JSON data specified"
            )
        },
        504: {
            "description": (
                "(Gateway Timeout) The webhook did not respond in time"
            )
        },
    }
)
def agents_status_post(job_id, json_data):
    """Post job status updates to the specified webhook URL.

    The `job_status_webhook` parameter is required for this endpoint.
    Other parameters included here will be forwarded to the webhook.

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
@v1.input(schema=schemas.JobId, location="path", arg_name="job_id")
@v1.output(
    str,
    status_code=200,
    description=(
        "(OK) Zero-based position indicating how many jobs are ahead "
        "of this job in the queue."
    ),
)
@v1.doc(
    responses={
        400: {"description": "(Bad Request) Invalid job_id specified"},
        410: {"description": "(Gone) Job not found or already started"},
    }
)
def job_position_get(job_id):
    """Return the position of the specified job_id in the queue."""
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
@v1.input(schema=schemas.QueueList, location="query", arg_name="queue")
@v1.output(
    schemas.QueueWaitTimePercentilesOut,
    status_code=200,
    description=(
        "(OK) JSON mapping of queue names to wait time metrics percentiles"
    ),
    example={
        "myqueue": {"5": 2.0, "10": 5.0, "50": 15.0, "90": 45.0, "95": 60.0},
        "otherqueue": {"5": 10.0, "10": 20.0, "50": 60.0, "90": 100.0, "95": 180.0},
    },
)
def queue_wait_time_percentiles_get():
    """Get wait time metrics for queues.

    Returns percentile statistics (p5, p10, p50, p90, p95) for job wait
    times in the specified queues. If no queues are specified, returns
    metrics for all queues.
    """
    queues = request.args.getlist("queue")
    wait_times = database.get_queue_wait_times(queues)
    queue_percentile_data = {}
    for queue in wait_times:
        queue_percentile_data[queue["name"]] = database.calculate_percentiles(
            queue["wait_times"]
        )
    return queue_percentile_data


@v1.get("/queues/<queue_name>/agents")
@v1.input(schemas.QueueName, location="path", arg_name="queue_name")
@v1.output(
    schemas.AgentOut(many=True),
    status_code=200,
    description=(
        "JSON data with an array of agent objects listening to the "
        "specified queue, including the agent state, location, and "
        "current job information."
    ),
)
@v1.doc(
    responses={
        204: {
            "description": (
                "(No Content) No agents found listening to the specified queue"
            )
        },
        404: {
            "description": ("(Not Found) The specified queue does not exist")
        },
    }
)
def get_agents_on_queue(queue_name):
    """Get the list of all data for agents listening to a specified queue."""
    if not database.queue_exists(queue_name):
        abort(
            HTTPStatus.NOT_FOUND,
            message=f"Queue '{queue_name}' does not exist.",
        )

    agents = database.get_agents_on_queue(queue_name)
    if not agents:
        return [], HTTPStatus.NO_CONTENT
    return agents


@v1.get("/queues/<queue_name>/jobs")
@v1.input(schemas.QueueName, location="path", arg_name="queue_name")
@v1.output(
    schemas.JobInQueueOut(many=True),
    status_code=200,
    description=(
        "JSON data with an array of job objects including job_id, "
        "created_at timestamp, job_state, and job_queue for all jobs "
        "in the specified queue."
    ),
)
@v1.doc(
    responses={
        204: {
            "description": (
                "(No Content) No jobs found in the specified queue"
            )
        },
    }
)
def get_jobs_by_queue(queue_name):
    """Get the jobs in a specified queue along with their state.

    Returns JSON data with an array of job objects including job_id,
    created_at timestamp, job_state, and job_queue for all jobs in the
    specified queue.
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
@v1.auth_required(
    auth=security.HTTPBasicAuth(
        description="Base64 encoded pair of client_id:client_key"
    )
)
@v1.output(
    schemas.Oauth2Token,
    status_code=200,
    description=(
        "(OK) JSON object containing access token, token type, "
        "expiration time, and refresh token"
    ),
    example={
        "access_token": "<JWT Access Token>",
        "token_type": "Bearer",
        "expires_in": 30,
        "refresh_token": "<Refresh Token>",
    },
)
@v1.doc(
    responses={
        401: {"description": "(Unauthorized) Invalid client id or client key"},
    }
)
def retrieve_token():
    """
    Issue both access token and refresh token for a client.

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
    Notes:
    - `expires_in` is the lifetime (in seconds) of the access token.
    - Refresh tokens default to 30 days; admin may issue non-expiring
      tokens for trusted integrations.

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
    access_token = auth.generate_access_token(allowed_resources, secret_key)

    role = allowed_resources.get("role")
    if role in (ServerRoles.ADMIN, ServerRoles.MANAGER):
        refresh_expires_in = None
    else:
        refresh_expires_in = 30 * 24 * 60 * 60  # 30 days in seconds

    refresh_token = auth.generate_refresh_token(
        client_id, expires_in=refresh_expires_in
    )

    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": 30,
        "refresh_token": refresh_token,
    }


@v1.post("/oauth2/refresh")
@v1.input(
    schema=schemas.Oauth2RefreshTokenIn,
    location="json",
    example={"refresh_token": "<opaque-refresh-token>"},
)
@v1.output(
    schemas.Oauth2RefreshTokenOut,
    status_code=200,
    description=(
        "(OK) JSON object containing new access token, token type, "
        "and expiration time"
    ),
    example={
        "access_token": "<new-JWT-Access-Token>",
        "token_type": "Bearer",
        "expires_in": 30,
    },
)
@v1.doc(
    responses={
        400: {
            "description": (
                "(Bad Request) Missing, invalid, revoked, or expired "
                "refresh token"
            )
        },
    }
)
def refresh_access_token():
    """Refresh access token using a valid refresh token."""
    data = request.get_json()
    refresh_token = data.get("refresh_token")
    if not refresh_token:
        abort(HTTPStatus.BAD_REQUEST, "Error: Missing refresh token.")

    token_entry = auth.validate_refresh_token(refresh_token)
    client_id = token_entry["client_id"]

    client_permissions = database.get_client_permissions(client_id)
    secret_key = os.environ.get("JWT_SIGNING_KEY")
    access_token = auth.generate_access_token(client_permissions, secret_key)

    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": 30,
    }


@v1.post("/oauth2/revoke")
@v1.input(
    schema=schemas.Oauth2RefreshTokenIn,
    location="json",
    example={"refresh_token": "<opaque-refresh-token>"},
)
@v1.output(
    str,
    status_code=200,
    description=(
        "(OK) Text response indicating successful revocation of the "
        "refresh token"
    ),
    example={"message": "Refresh token revoked successfully"},
)
@v1.doc(
    responses={
        400: {
            "description": (
                "(Bad Request) Missing, invalid, or already revoked "
                "refresh token"
            )
        },
        401: {
            "description": (
                "(Unauthorized) Admin privileges required to revoke "
                "refresh tokens"
            )
        },
    }
)
@authenticate
@require_role(ServerRoles.ADMIN)
def revoke_refresh_token():
    """Revoke a refresh token. Only admins can perform this action."""
    data = request.get_json()
    token = data.get("refresh_token")
    if not token:
        abort(HTTPStatus.BAD_REQUEST, "Error: Missing refresh token.")

    token_entry = database.get_refresh_token_by_token(token)
    if not token_entry:
        abort(HTTPStatus.BAD_REQUEST, "Refresh token not found")

    if token_entry.get("revoked"):
        abort(HTTPStatus.BAD_REQUEST, "Refresh token has already been revoked")

    database.edit_refresh_token(token, {"revoked": True})

    return {"status": "OK"}


@v1.get("/restricted-queues")
@authenticate
@require_role(ServerRoles.ADMIN, ServerRoles.MANAGER, ServerRoles.CONTRIBUTOR)
@v1.output(schemas.RestrictedQueueOut(many=True))
@v1.auth_required(
    auth=security.HTTPTokenAuth(
        scheme="Bearer",
        description=(
            "Based64-encoded JWT access token with permissions to "
            "access restricted queues"
        ),
    )
)
@v1.doc(
    responses={
        401: {
            "description": ("(Unauthorized) Missing or invalid access token")
        },
        403: {
            "description": (
                "(Forbidden) Insufficient permissions for the "
                "authenticated user to access restricted queues"
            )
        },
    }
)
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
@v1.input(schemas.QueueName, location="path", arg_name="queue_name")
@v1.auth_required(
    auth=security.HTTPTokenAuth(
        scheme="Bearer",
        description=(
            "Based64-encoded JWT access token with permissions to "
            "access restricted queues"
        ),
    )
)
@v1.doc(
    responses={
        401: {
            "description": ("(Unauthorized) Missing or invalid access token")
        },
        403: {
            "description": (
                "(Forbidden) Insufficient permissions for the "
                "authenticated user to access restricted queues"
            )
        },
        404: {
            "description": (
                "(Not Found) The specified restricted queue was not found"
            )
        },
    }
)
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
@v1.input(
    schemas.RestrictedQueueIn,
    location="json",
    example={"client_id": "myclient"},
)
@v1.input(schemas.QueueName, location="path", arg_name="queue_name")
@v1.auth_required(
    auth=security.HTTPTokenAuth(
        scheme="Bearer",
        description=(
            "Based64-encoded JWT access token with admin or manager "
            "permissions"
        ),
    )
)
@v1.doc(
    responses={
        400: {
            "description": (
                "(Bad Request) Missing client_id to set as owner of "
                "restricted queue"
            )
        },
        401: {
            "description": ("(Unauthorized) Missing or invalid access token")
        },
        403: {
            "description": (
                "(Forbidden) Insufficient permissions for the "
                "authenticated user to associate restricted queues"
            )
        },
        404: {
            "description": (
                "(Not Found) The specified restricted queue does not "
                "exist or is not associated to an agent"
            )
        },
    }
)
@authenticate
@require_role(ServerRoles.ADMIN, ServerRoles.MANAGER)
def add_restricted_queue(queue_name: str, json_data: dict) -> dict:
    """Add an owner to the specific restricted queue.
    If the queue does not exist yet, it will be created automatically.
    """
    client_id = json_data.get("client_id", "")

    # Validate client ID is available in request data
    if not client_id:
        abort(HTTPStatus.BAD_REQUEST, "Error: Missing client ID.")

    # Validate client ID exists in database
    if not database.check_client_exists(client_id):
        abort(
            HTTPStatus.NOT_FOUND,
            "Error: Specified client_id does not exist.",
        )

    if not database.queue_exists(queue_name):
        abort(
            HTTPStatus.NOT_FOUND,
            "Error: No agent is associated with the specified queue.",
        )

    database.add_restricted_queue(queue_name, client_id)

    return "OK"


@v1.delete("/restricted-queues/<queue_name>")
@v1.input(
    schemas.RestrictedQueueIn,
    location="json",
    example={"client_id": "myclient"},
)
@v1.input(schemas.QueueName, location="path", arg_name="queue_name")
@v1.auth_required(
    auth=security.HTTPTokenAuth(
        scheme="Bearer",
        description=(
            "Based64-encoded JWT access token with admin or manager "
            "permissions"
        ),
    )
)
@v1.doc(
    responses={
        400: {
            "description": (
                "(Bad Request) Missing client_id to remove as owner "
                "of restricted queue"
            )
        },
        401: {
            "description": ("(Unauthorized) Missing or invalid access token")
        },
        403: {
            "description": (
                "(Forbidden) Insufficient permissions for the "
                "authenticated user to remove restricted queues"
            )
        },
        404: {
            "description": (
                "(Not Found) The specified queue was not found or it "
                "is not in the restricted queue list"
            )
        },
    }
)
@authenticate
@require_role(ServerRoles.ADMIN, ServerRoles.MANAGER)
def delete_restricted_queue(queue_name: str, json_data: dict) -> dict:
    """Delete an owner from the specific restricted queue."""
    if not database.check_queue_restricted(queue_name):
        abort(HTTPStatus.NOT_FOUND, "Error: Restricted queue not found.")

    client_id = json_data.get("client_id", "")
    if not client_id:
        abort(HTTPStatus.BAD_REQUEST, "Error: Missing client ID.")

    database.delete_restricted_queue(queue_name, client_id)

    return "OK"


@v1.get("/client-permissions")
@authenticate
@require_role(ServerRoles.ADMIN, ServerRoles.MANAGER)
@v1.output(
    schemas.ClientPermissionsOut(many=True),
    description=(
        "JSON data with a list all client IDs and its permission "
        "excluding the hashed secret stored in database"
    ),
)
@v1.auth_required(
    auth=security.HTTPTokenAuth(
        scheme="Bearer",
        description=(
            "Based64-encoded JWT access token with admin or manager "
            "permissions"
        ),
    )
)
@v1.doc(
    responses={
        401: {
            "description": ("(Unauthorized) Missing or invalid access token")
        },
        403: {
            "description": (
                "(Forbidden) Insufficient permissions for the "
                "authenticated user"
            )
        },
    }
)
def get_all_client_permissions() -> list[dict]:
    """Retrieve all all client_id and their permissions from database."""
    return database.get_client_permissions()


@v1.get("/client-permissions/<client_id>")
@authenticate
@require_role(ServerRoles.ADMIN, ServerRoles.MANAGER)
@v1.output(
    schemas.ClientPermissionsOut,
    description=(
        "JSON data with the permissions of a specified client "
        "excluding the hashed secret stored in database"
    ),
)
@v1.input(schemas.ClientId, location="path", arg_name="client_id")
@v1.auth_required(
    auth=security.HTTPTokenAuth(
        scheme="Bearer",
        description=(
            "Based64-encoded JWT access token with admin or manager "
            "permissions"
        ),
    )
)
@v1.doc(
    responses={
        401: {
            "description": ("(Unauthorized) Missing or invalid access token")
        },
        403: {
            "description": (
                "(Forbidden) Insufficient permissions for the "
                "authenticated user"
            )
        },
        404: {
            "description": (
                "(Not Found) The specified client_id was not found"
            )
        },
    }
)
def get_client_permissions(client_id) -> list[dict]:
    """Retrieve single client-permissions from database."""
    if not database.check_client_exists(client_id):
        abort(
            HTTPStatus.NOT_FOUND,
            "Error: Specified client_id does not exist.",
        )

    return database.get_client_permissions(client_id)


@v1.put("/client-permissions/<client_id>")
@authenticate
@require_role(ServerRoles.ADMIN, ServerRoles.MANAGER)
@v1.input(
    schemas.ClientPermissionsIn,
    location="json",
    example={
        "client_id": "myclient",
        "client_secret": "my-secret-password",
        "max_priority": {},
        "max_reservation_time": {"*": 40000},
        "role": "contributor",
    },
)
@v1.input(schemas.ClientId, location="path", arg_name="client_id")
@v1.auth_required(
    auth=security.HTTPTokenAuth(
        scheme="Bearer",
        description=(
            "Based64-encoded JWT access token with admin or manager "
            "permissions"
        ),
    )
)
@v1.doc(
    responses={
        400: {
            "description": (
                "(Bad Request) Missing client_secret when creating "
                "new client permissions"
            )
        },
        401: {
            "description": ("(Unauthorized) Missing or invalid access token")
        },
        403: {
            "description": (
                "(Forbidden) Insufficient permissions for the "
                "authenticated user to modify client permissions"
            )
        },
        404: {
            "description": (
                "(Not Found) The specified client_id was not found"
            )
        },
        422: {
            "description": (
                "(Unprocessable Entity) System admin client cannot be "
                "modified using the API"
            )
        },
    }
)
def set_client_permissions(client_id: str, json_data: dict) -> str:
    """Add or create client permissions for a specified user."""
    # Testflinger Admin credential can't be modified from API!'
    if client_id == TESTFLINGER_ADMIN_ID:
        abort(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "Error: System admin client cannot by modified from API.",
        )

    client_secret = json_data.pop("client_secret", None)
    permissions = database.get_client_permissions(client_id) or {}
    client_exist = bool(permissions)
    # Default role for backward compatibility
    current_role = permissions.get("role", ServerRoles.CONTRIBUTOR)

    # validation: client secret is required when creating permissions
    if not client_exist and not client_secret:
        abort(
            HTTPStatus.BAD_REQUEST,
            "Error: Missing client_secret in request body for new client",
        )

    if client_secret:
        client_secret_hash = auth.hash_secret(client_secret)
        json_data["client_secret_hash"] = client_secret_hash

    # validation: the requesting client can modify the client't permissions
    # only if its role is not inferior to the client's role
    if ServerRoles(g.role) < ServerRoles(current_role):
        abort(
            HTTPStatus.FORBIDDEN,
            f"{g.client_id} has insufficient permissions "
            f"to modify client '{client_id}'",
        )

    # validation: the requesting client can modify the client't role
    # only if its role is not inferior to the client's new role
    new_role = json_data.get("role", None)
    if new_role and ServerRoles(g.role) < ServerRoles(new_role):
        abort(
            HTTPStatus.FORBIDDEN,
            f"{g.client_id} has insufficient permissions "
            f"to assign role '{new_role}' to client '{client_id}'",
        )

    # Update permissions from json data
    permissions.update(json_data)
    database.create_or_update_client_permissions(client_id, permissions)

    if client_exist:
        return f"Updated permissions for client '{client_id}'"
    else:
        return f"Created permissions for client '{client_id}'"


@v1.delete("/client-permissions/<client_id>")
@authenticate
@require_role(ServerRoles.ADMIN)
@v1.input(schemas.ClientId, location="path", arg_name="client_id")
@v1.auth_required(
    auth=security.HTTPTokenAuth(
        scheme="Bearer",
        description=(
            "Based64-encoded JWT access token with admin permissions"
        ),
    )
)
@v1.doc(
    responses={
        401: {
            "description": ("(Unauthorized) Missing or invalid access token")
        },
        403: {
            "description": (
                "(Forbidden) Insufficient permissions for the "
                "authenticated user to delete client permissions"
            )
        },
        404: {
            "description": (
                "(Not Found) The specified client_id was not found"
            )
        },
        422: {
            "description": (
                "(Unprocessable Entity) System admin can't be "
                "removed using the API"
            )
        },
    }
)
def delete_client_permissions(client_id: str) -> str:
    """Delete client id along with its permissions."""
    # Testflinger Admin credential can't be removed from API!'
    if client_id == TESTFLINGER_ADMIN_ID:
        abort(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "Error: System admin client cannot by deleted from API.",
        )
    if not database.check_client_exists(client_id):
        abort(
            HTTPStatus.NOT_FOUND,
            "Error: Specified client_id does not exist.",
        )

    # Delete entry from database
    database.delete_client_permissions(client_id)

    return "OK"


@v1.put("/secrets/<client_id>/<path:path>")
@authenticate
@v1.input(schemas.SecretIn, location="json")
@v1.input(schemas.ClientId, location="path", arg_name="client_id")
@v1.input(schemas.SecretPath, location="path", arg_name="path")
@v1.auth_required(
    auth=security.HTTPTokenAuth(
        scheme="Bearer",
        description=(
            "Based64-encoded JWT access token with permissions to "
            "store secrets"
        ),
    )
)
@v1.doc(
    responses={
        400: {
            "description": (
                "(Bad Request) No secrets store configured or access error"
            )
        },
        403: {
            "description": (
                "(Forbidden) client_id does not match authenticated client id"
            )
        },
        500: {
            "description": (
                "(Internal Server Error) Error storing the secret value"
            )
        },
    }
)
def secrets_put(client_id, path, json_data):
    """Store a secret value for the specified client_id and path."""
    if current_app.secrets_store is None:
        abort(HTTPStatus.BAD_REQUEST, message="No secrets store")
    if client_id != g.client_id:
        abort(
            HTTPStatus.FORBIDDEN,
            message=f"'{client_id}' doesn't match authenticated client id",
        )
    try:
        current_app.secrets_store.write(client_id, path, json_data["value"])
    except AccessError as error:
        abort(HTTPStatus.BAD_REQUEST, message=str(error))
    except (StoreError, UnexpectedError) as error:
        abort(HTTPStatus.INTERNAL_SERVER_ERROR, message=str(error))

    return "OK"


@v1.delete("/secrets/<client_id>/<path:path>")
@authenticate
@v1.input(schemas.ClientId, location="path", arg_name="client_id")
@v1.input(schemas.SecretPath, location="path", arg_name="path")
@v1.auth_required(
    auth=security.HTTPTokenAuth(
        scheme="Bearer",
        description=(
            "Based64-encoded JWT access token with permissions to "
            "delete secrets"
        ),
    )
)
@v1.doc(
    responses={
        400: {
            "description": (
                "(Bad Request) No secrets store configured or access error"
            )
        },
        403: {
            "description": (
                "(Forbidden) client_id does not match authenticated client id"
            )
        },
        500: {
            "description": (
                "(Internal Server Error) Error deleting the secret value"
            )
        },
    }
)
def secrets_delete(client_id, path):
    """Remove a secret value for the specified client_id and path."""
    if current_app.secrets_store is None:
        abort(HTTPStatus.BAD_REQUEST, message="No secrets store")
    if client_id != g.client_id:
        abort(
            HTTPStatus.FORBIDDEN,
            message=f"'{client_id}' doesn't match authenticated client id",
        )
    try:
        current_app.secrets_store.delete(client_id, path)
    except AccessError as error:
        abort(HTTPStatus.BAD_REQUEST, message=str(error))
    except (StoreError, UnexpectedError) as error:
        abort(HTTPStatus.INTERNAL_SERVER_ERROR, message=str(error))

    return "OK"


@v1.get("/result/<job_id>/output")
@v1.doc(deprecated=True)
def legacy_output_get(job_id: str) -> str:
    """Legacy endpoint to get job output for a specified job_id.

    TODO: Remove after CLI/agent migration completes.

    :param job_id: UUID as a string for the job
    :raises HTTPError: BAD_REQUEST when job_id is invalid
    :return: Plain text output
    """
    if not check_valid_uuid(job_id):
        abort(HTTPStatus.BAD_REQUEST, message="Invalid job_id specified")
    response = database.mongo.db.output.find_one_and_delete(
        {"job_id": job_id}, {"_id": False}
    )
    output = response.get("output", []) if response else None
    if output:
        return "\n".join(output)
    return "", HTTPStatus.NO_CONTENT


@v1.post("/result/<job_id>/output")
@v1.doc(deprecated=True)
def legacy_output_post(job_id: str) -> str:
    """Legacy endpoint to post output for a specified job_id.

    TODO: Remove after CLI/agent migration completes.

    :param job_id: UUID as a string for the job
    :raises HTTPError: BAD_REQUEST when job_id is invalid
    :return: "OK" on success
    """
    if not check_valid_uuid(job_id):
        abort(HTTPStatus.BAD_REQUEST, message="Invalid job_id specified")
    data = request.get_data().decode("utf-8")
    timestamp = datetime.now(timezone.utc)
    database.mongo.db.output.update_one(
        {"job_id": job_id},
        {"$set": {"updated_at": timestamp}, "$push": {"output": data}},
        upsert=True,
    )
    return "OK"


@v1.get("/result/<job_id>/serial_output")
@v1.doc(deprecated=True)
def legacy_serial_output_get(job_id: str) -> str:
    """Legacy endpoint to get latest serial output for a specified job ID.

    TODO: Remove after CLI/agent migration completes.

    :param job_id: UUID as a string for the job
    :raises HTTPError: BAD_REQUEST when job_id is invalid
    :return: Plain text serial output
    """
    if not check_valid_uuid(job_id):
        abort(HTTPStatus.BAD_REQUEST, message="Invalid job_id specified")
    response = database.mongo.db.serial_output.find_one_and_delete(
        {"job_id": job_id}, {"_id": False}
    )
    output = response.get("serial_output", []) if response else None
    if output:
        return "\n".join(output)
    return "", HTTPStatus.NO_CONTENT


@v1.post("/result/<job_id>/serial_output")
@v1.doc(deprecated=True)
def legacy_serial_output_post(job_id: str) -> str:
    """Legacy endpoint to post serial output for a specified job ID.

    TODO: Remove after CLI/agent migration completes.

    :param job_id: UUID as a string for the job
    :raises HTTPError: BAD_REQUEST when job_id is invalid
    :return: "OK" on success
    """
    if not check_valid_uuid(job_id):
        abort(HTTPStatus.BAD_REQUEST, message="Invalid job_id specified")
    data = request.get_data().decode("utf-8")
    timestamp = datetime.now(timezone.utc)
    database.mongo.db.serial_output.update_one(
        {"job_id": job_id},
        {"$set": {"updated_at": timestamp}, "$push": {"serial_output": data}},
        upsert=True,
    )
    return "OK"
