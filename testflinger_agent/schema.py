# Copyright (C) 2016 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import voluptuous

SCHEMA_V1 = {
    voluptuous.Required('agent_id'): str,
    'polling_interval': int,
    voluptuous.Required('server_address'): str,
    'execution_basedir': str,
    'logging_basedir': str,
    voluptuous.Required('job_queues'): list,
    'setup_command': str,
    'provision_command': str,
    'test_command': str,
}


def validate(data):
    """Validate data according to known schemas

    :param data:
        Data to validate
    """
    v1 = voluptuous.Schema(SCHEMA_V1)
    v1(data)
