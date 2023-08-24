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

import uuid
from apiflask import Schema, fields
from apiflask.validators import OneOf


class AgentIn(Schema):
    """Agent data schema"""

    state = fields.String(required=False)
    queues = fields.List(fields.String(), required=False)
    location = fields.String(required=False)
    job_id = fields.String(required=False)
    log = fields.List(fields.String(), required=False)


class ActionIn(Schema):
    """Action data schema"""

    action = fields.String(required=True, validate=OneOf(["cancel"]))


class JobIn(Schema):
    job_id = fields.String(required=False)
    job_queue = fields.String(required=True)
    global_timeout = fields.Integer(required=False)
    output_timeout = fields.Integer(required=False)
    provision_data = fields.Dict(required=False)
    test_data = fields.Dict(required=False)
    allocate_data = fields.Dict(required=False)
    recover_data = fields.Dict(required=False)


class JobOut(Schema):
    job_id = fields.String(required=True)
