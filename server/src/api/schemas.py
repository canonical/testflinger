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


class AgentIn(Schema):
    """Agent data input schema"""

    identifier = fields.String(required=False)
    job_id = fields.String(required=False)
    location = fields.String(required=False)
    log = fields.List(fields.String(), required=False)
    queues = fields.List(fields.String(), required=False)
    state = fields.String(required=False)


class AgentOut(Schema):
    """Agent data input schema"""

    state = fields.String(required=False)
    queues = fields.List(fields.String(), required=False)
    location = fields.String(required=False)
    job_id = fields.String(required=False)


class ActionIn(Schema):
    """Action data input schema"""

    action = fields.String(required=True, validate=OneOf(["cancel"]))


class Job(Schema):
    """Job schema"""

    job_id = fields.String(required=False)
    parent_job_id = fields.String(required=False)
    name = fields.String(required=False)
    job_queue = fields.String(required=True)
    global_timeout = fields.Integer(required=False)
    output_timeout = fields.Integer(required=False)
    allocation_timeout = fields.Integer(required=False)
    provision_data = fields.Dict(required=False)
    firmware_update_data = fields.Dict(required=False)
    test_data = fields.Dict(required=False)
    allocate_data = fields.Dict(required=False)
    reserve_data = fields.Dict(required=False)


class JobId(Schema):
    """Job ID schema"""

    job_id = fields.String(required=True)


class Result(Schema):
    """Result schema"""

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
