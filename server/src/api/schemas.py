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
Testflinger v1 OpenAPI schemas
"""

from apiflask import Schema, fields
from apiflask.validators import OneOf


ValidJobStates = (
    "setup",
    "provision",
    "firmware_update",
    "test",
    "allocate",
    "allocated",
    "reserve",
    "cleanup",
    "cancelled",
    "completed",
    "active",  # fake state for jobs that are not completed or cancelled
)


class ProvisionLogsIn(Schema):
    """Provision logs input schema"""

    job_id = fields.String(required=True)
    exit_code = fields.Integer(required=True)
    detail = fields.String(required=False)


class AgentIn(Schema):
    """Agent data input schema"""

    identifier = fields.String(required=False)
    job_id = fields.String(required=False)
    location = fields.String(required=False)
    log = fields.List(fields.String(), required=False)
    provision_type = fields.String(required=False)
    queues = fields.List(fields.String(), required=False)
    state = fields.String(required=False)


class AgentOut(Schema):
    """Agent data input schema"""

    state = fields.String(required=False)
    queues = fields.List(fields.String(), required=False)
    location = fields.String(required=False)
    provision_type = fields.String(required=False)
    job_id = fields.String(required=False)


class ActionIn(Schema):
    """Action data input schema"""

    action = fields.String(required=True, validate=OneOf(["cancel"]))


class Attachment(Schema):
    """Attachment pathnames schema

    - `agent`: path to copy the attachment in the testflinger agent (optional)
    - `device`: path to copy the attachment in the device under test (optional)
    """

    agent = fields.String(required=True)
    device = fields.String(required=False)


class TestData(Schema):
    """Schema for the `test_data` section of a testflinger job"""

    test_cmds = fields.String(required=False)
    attachments = fields.List(fields.Nested(Attachment), required=False)
    # [TODO] Suggest removing these: introduce an `environment` field
    # that specifies values for environment variables
    test_username = fields.String(required=False)
    test_password = fields.String(required=False)


class Job(Schema):
    """Job schema"""

    job_id = fields.String(required=False)
    parent_job_id = fields.String(required=False)
    name = fields.String(required=False)
    tags = fields.List(fields.String(), required=False)
    job_queue = fields.String(required=True)
    global_timeout = fields.Integer(required=False)
    output_timeout = fields.Integer(required=False)
    allocation_timeout = fields.Integer(required=False)
    # [TODO] specify Nested schema to improve validation,
    # i.e. expected fields within `provision_data`
    provision_data = fields.Dict(required=False)
    # [TODO] specify Nested schema to improve validation,
    # i.e. expected fields within `firmware_update_data`
    firmware_update_data = fields.Dict(required=False)
    test_data = fields.Nested(TestData, required=False)
    allocate_data = fields.Dict(required=False)
    reserve_data = fields.Dict(required=False)
    job_status_webhook = fields.String(required=False)
    job_priority = fields.Integer(required=False)


class JobId(Schema):
    """Job ID schema"""

    job_id = fields.String(required=True)


class JobSearchRequest(Schema):
    """Job search request schema"""

    tags = fields.List(fields.String, description="List of tags to search for")
    match = fields.String(
        description="Match mode - 'all' or 'any' (default 'any')",
        validate=OneOf(["any", "all"]),
    )
    state = fields.List(
        fields.String(validate=OneOf(ValidJobStates)),
        description="List of job states to include",
    )


class JobSearchResponse(Schema):
    """Job search response schema"""

    jobs = fields.List(fields.Nested(Job), required=True)


class Result(Schema):
    """Result schema"""

    unpack_status = fields.Integer(required=False)
    unpack_output = fields.String(required=False)
    unpack_serial = fields.String(required=False)
    setup_status = fields.Integer(required=False)
    setup_output = fields.String(required=False)
    setup_serial = fields.String(required=False)
    provision_status = fields.Integer(required=False)
    provision_output = fields.String(required=False)
    provision_serial = fields.String(required=False)
    firmware_update_status = fields.Integer(required=False)
    firmware_update_output = fields.String(required=False)
    firmware_update_serial = fields.String(required=False)
    test_status = fields.Integer(required=False)
    test_output = fields.String(required=False)
    test_serial = fields.String(required=False)
    allocate_status = fields.Integer(required=False)
    allocate_output = fields.String(required=False)
    allocate_serial = fields.String(required=False)
    reserve_status = fields.Integer(required=False)
    reserve_output = fields.String(required=False)
    reserve_serial = fields.String(required=False)
    cleanup_status = fields.Integer(required=False)
    cleanup_output = fields.String(required=False)
    cleanup_serial = fields.String(required=False)
    device_info = fields.Dict(required=False)
    job_state = fields.String(required=False)


class JobEvent(Schema):
    """Job Event schema"""

    event_name = fields.String(required=True)
    timestamp = fields.String(required=True)
    detail = fields.String(required=False)


class StatusUpdate(Schema):
    """Status Update schema"""

    agent_id = fields.String(required=False)
    job_queue = fields.String(required=False)
    job_status_webhook = fields.URL(required=True)
    events = fields.List(fields.Nested(JobEvent), required=False)


job_empty = {
    204: {
        "description": "No job found",
        "content": {
            "application/json": {
                "schema": {"type": "object", "properties": {}}
            }
        },
    }
}

queues_out = {
    200: {
        "description": "Mapping of queue names and descriptions",
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "string",
                    },
                    "example": {
                        "device001": "Queue for device001",
                        "some-queue": "some other queue",
                    },
                },
            },
        },
    },
}

images_out = {
    200: {
        "description": "Mapping of image names and provision data",
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "string",
                    },
                    "example": {
                        "core22": "url: http://.../core22.img.xz",
                        "server-22.04": "url: http://.../ubuntu-22.04.img.xz",
                    },
                },
            },
        },
    },
}
