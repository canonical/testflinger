# Copyright (C) 2026 Canonical
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
"""Render job data as YAML."""

import yaml

from testflinger.api.schemas import Job

# Fields the server assigns; never part of a resubmittable job definition.
_SERVER_MANAGED_JOB_FIELDS = frozenset({"job_id", "parent_job_id"})

# Submittable job-definition fields, derived from the Job schema in declaration
# order. Deriving (rather than hard-coding) means new submittable fields added
# to the schema appear in the copied YAML automatically; only server-managed
# fields need excluding above.
JOB_DEFINITION_FIELDS = tuple(
    name for name in Job().fields if name not in _SERVER_MANAGED_JOB_FIELDS
)


class _JobYamlDumper(yaml.SafeDumper):
    """YAML dumper that renders multiline strings as literal blocks."""


def _str_representer(dumper, data):
    """Represent multiline strings (e.g. test_cmds) as literal blocks."""
    if "\n" in data:
        # remove trailing whitespace from each line
        # (suggested fix for https://github.com/yaml/pyyaml/issues/240)
        data = "\n".join(line.rstrip() for line in data.splitlines()) + "\n"
        return dumper.represent_scalar(
            "tag:yaml.org,2002:str", data, style="|"
        )
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_JobYamlDumper.add_representer(str, _str_representer)


def dump_yaml(data):
    """Dump a value to YAML using the literal-block-aware dumper."""
    return yaml.dump(
        data,
        Dumper=_JobYamlDumper,
        default_flow_style=False,
        sort_keys=False,
    )


def build_job_yaml(job_data):
    """Build a submittable job-definition YAML from stored job data."""
    definition = {
        field: job_data[field]
        for field in JOB_DEFINITION_FIELDS
        if field in job_data
    }
    return dump_yaml(definition)
