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
"""Testflinger v1 OpenAPI schemas."""

from apiflask import Schema, fields
from apiflask.validators import Length, OneOf, Regexp
from marshmallow import ValidationError, validates_schema
from marshmallow_oneofschema import OneOfSchema

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
    """Provision logs input schema."""

    job_id = fields.String(required=True)
    exit_code = fields.Integer(required=True)
    detail = fields.String(required=False)


class AgentIn(Schema):
    """Agent data input schema."""

    identifier = fields.String(required=False)
    job_id = fields.String(required=False)
    location = fields.String(required=False)
    log = fields.List(fields.String(), required=False)
    provision_type = fields.String(required=False)
    queues = fields.List(fields.String(), required=False)
    state = fields.String(required=False)
    comment = fields.String(required=False)


class AgentOut(Schema):
    """Agent data output schema."""

    name = fields.String(required=True)
    state = fields.String(required=False)
    queues = fields.List(fields.String(), required=False)
    location = fields.String(required=False)
    provision_type = fields.String(required=False)
    job_id = fields.String(required=False)
    comment = fields.String(required=False)
    restricted_to = fields.Dict(required=False)


class ActionIn(Schema):
    """Action data input schema."""

    action = fields.String(required=True, validate=OneOf(["cancel"]))


class Attachment(Schema):
    """Attachment pathnames schema.

    - `agent`: path to copy the attachment in the testflinger agent (optional)
    - `device`: path to copy the attachment in the device under test (optional)
    """

    agent = fields.String(required=True)
    device = fields.String(required=False)


class CM3ProvisionData(Schema):
    """Schema for the `provision_data` section of a CM3 job."""

    url = fields.URL(required=True)


class MAASProvisionData(Schema):
    """Schema for the `provision_data` section of a MAAS job."""

    distro = fields.String(required=False)
    kernel = fields.String(required=False)
    user_data = fields.String(required=False)
    # [TODO] Specify Nested schema to improve validation
    disks = fields.List(fields.Dict(), required=False)


class MultiProvisionData(Schema):
    """Schema for the `provision_data` section of a Multi-device job."""

    # [TODO] Specify Nested schema to improve validation
    jobs = fields.List(fields.Dict(), required=True, validate=Length(min=1))


class MuxPiProvisionData(Schema):
    """Schema for the `provision_data` section of a MuxPi job."""

    url = fields.URL(required=False)
    use_attachment = fields.String(required=False)
    attachments = fields.List(fields.Nested(Attachment), required=False)
    create_user = fields.Boolean(required=False)
    boot_check_url = fields.String(required=False)
    media = fields.String(validate=OneOf(["sd", "usb"]), required=False)

    @validates_schema
    def validate_image(self, data, **_):
        """Validate that either `url` or `use_attachment` is provided."""
        if "url" not in data and "use_attachment" not in data:
            raise ValidationError(
                "Either 'url' or 'use_attachment' must be provided."
            )


class NoProvisionData(Schema):
    """Schema for the `provision_data` section of a no-provision job."""

    skip = fields.Boolean(required=False, default=True)


class OEMAutoinstallProvisionData(Schema):
    """Schema for the `provision_data` section of a OEM Autoinstall job."""

    url = fields.URL(required=True)
    token_file = fields.String(required=False)
    user_data = fields.String(required=False)
    redeploy_cfg = fields.String(required=False)
    authorized_keys = fields.String(required=False)


class OEMScriptProvisionData(Schema):
    """Schema for the `provision_data` section of a OEM Script job."""

    url = fields.URL(required=True)


class BaseZapperProvisionData(Schema):
    """Shared schema for the `provision_data` of Zapper jobs."""

    zapper_provisioning_timeout = fields.Integer(required=False)


class ZapperIoTPresetProvisionData(BaseZapperProvisionData):
    """Schema for the `provision_data` section of a Zapper IoT job.

    This schema is used when using a preset for provisioning.
    """

    urls = fields.List(fields.URL(), required=True, validate=Length(min=1))
    preset = fields.String(required=True)


class ZapperIoTCustomProvisionData(BaseZapperProvisionData):
    """Schema for the `provision_data` section of a Zapper IoT job.

    This schema is used when using a custom plan for provisioning.
    """

    urls = fields.List(fields.URL(), required=True, validate=Length(min=1))
    ubuntu_sso_email = fields.Email(required=False)
    # [TODO] Specify Nested schema to improve validation
    provision_plan = fields.Dict(required=True)


class ZapperKVMAutoinstallProvisionData(BaseZapperProvisionData):
    """Schema for the `provision_data` section of a Zapper KVM job.

    This schema is used to target autoinstall-driven provisioning.
    """

    url = fields.URL(required=True)
    robot_tasks = fields.List(fields.String(), required=True)
    autoinstall_storage_layout = fields.String(required=False)
    ubuntu_sso_email = fields.Email(required=False)
    autoinstall_base_user_data = fields.String(required=False)
    autoinstall_oem = fields.Boolean(required=False)
    cmdline_append = fields.String(required=False)


class ZapperKVMOEM2204ProvisionData(BaseZapperProvisionData):
    """Schema for the `provision_data` section of a Zapper KVM job.

    This schema is used to target Ubuntu OEM 22.04.
    """

    alloem_url = fields.URL(required=True)
    robot_tasks = fields.List(fields.String(), required=True)
    url = fields.URL(required=False)
    oem = fields.String(required=False)


class ZapperKVMGenericProvisionData(BaseZapperProvisionData):
    """Schema for the `provision_data` section of a Zapper KVM job.

    This schema is used to target any generic live ISOs.
    """

    url = fields.URL(required=True)
    robot_tasks = fields.List(fields.String(), required=True)
    live_image = fields.Boolean(required=True)
    wait_until_ssh = fields.Boolean(required=True)


class ProvisionData(OneOfSchema):
    """Polymorphic schema for the `provision_data` section of a job."""

    type_schemas = {
        "cm3": CM3ProvisionData,
        "maas": MAASProvisionData,
        "multi": MultiProvisionData,
        "muxpi": MuxPiProvisionData,
        "noprovision": NoProvisionData,
        "oem_autoinstall": OEMAutoinstallProvisionData,
        "oem_script": OEMScriptProvisionData,
        "zapper_iot_preset": ZapperIoTPresetProvisionData,
        "zapper_iot_custom": ZapperIoTCustomProvisionData,
        "zapper_kvm_autoinstall": ZapperKVMAutoinstallProvisionData,
        "zapper_kvm_oem_2204": ZapperKVMOEM2204ProvisionData,
        "zapper_kvm_generic": ZapperKVMGenericProvisionData,
    }

    def get_obj_type(self, obj):
        """Get object type depending on which schema is correctly parsed."""
        return self.get_data_type(obj)

    def get_data_type(self, data):
        """Get schema type depending on which schema is correctly parsed."""
        if data is None:
            return "noprovision"
        for slug, schema in self.type_schemas.items():
            try:
                schema().load(data)
                return slug
            except ValidationError:
                continue
        raise ValidationError("Invalid provision data schema.")

    def _dump(self, obj, **kwargs):
        result = super()._dump(obj, **kwargs)
        # Parent dump injects the type field:
        #   result[self.type_field] = self.get_obj_type(obj)
        # So we need to remove it
        result.pop(self.type_field)
        return result


class TestData(Schema):
    """Schema for the `test_data` section of a testflinger job."""

    test_cmds = fields.String(required=False)
    attachments = fields.List(fields.Nested(Attachment), required=False)
    # [TODO] Suggest removing these: introduce an `environment` field
    # that specifies values for environment variables
    test_username = fields.String(required=False)
    test_password = fields.String(required=False)


class ReserveData(Schema):
    """Schema for the `reserve_data` section of a Testflinger job."""

    ssh_keys = fields.List(
        fields.String(validate=Regexp(r"^(lp|gh):(\S+)$")), required=False
    )
    timeout = fields.Integer(required=False)


class Job(Schema):
    """Job schema."""

    job_id = fields.String(required=False)
    parent_job_id = fields.String(required=False)
    name = fields.String(required=False)
    tags = fields.List(fields.String(), required=False)
    job_queue = fields.String(required=True)
    global_timeout = fields.Integer(required=False)
    output_timeout = fields.Integer(required=False)
    allocation_timeout = fields.Integer(required=False)
    provision_data = fields.Nested(
        ProvisionData, required=False, allow_none=True
    )
    # [TODO] specify Nested schema to improve validation,
    # i.e. expected fields within `firmware_update_data`
    firmware_update_data = fields.Dict(required=False)
    test_data = fields.Nested(TestData, required=False)
    allocate_data = fields.Dict(required=False)
    reserve_data = fields.Nested(ReserveData, required=False)
    job_status_webhook = fields.String(required=False)
    job_priority = fields.Integer(required=False)


class JobId(Schema):
    """Job ID schema."""

    job_id = fields.String(required=True)


class JobSearchRequest(Schema):
    """Job search request schema."""

    tags = fields.List(
        fields.String,
        metadata={"description": "List of tags to search for"},
    )
    match = fields.String(
        validate=OneOf(["any", "all"]),
        metadata={
            "description": "Match mode - 'all' or 'any' (default 'any')"
        },
    )
    state = fields.List(
        fields.String(validate=OneOf(ValidJobStates)),
        metadata={"description": "List of job states to include"},
    )


class JobSearchResponse(Schema):
    """Job search response schema."""

    jobs = fields.List(fields.Nested(Job), required=True)


class Result(Schema):
    """Result schema."""

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
    """Job Event schema."""

    event_name = fields.String(required=True)
    timestamp = fields.String(required=True)
    detail = fields.String(required=False)


class StatusUpdate(Schema):
    """Status Update schema."""

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
