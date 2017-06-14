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
    voluptuous.Required('polling_interval', default=10): int,
    voluptuous.Required('server_address'): str,
    voluptuous.Required('execution_basedir',
                        default='/tmp/testflinger/run'): str,
    voluptuous.Required('logging_basedir',
                        default='/tmp/testflinger/logs'): str,
    voluptuous.Required('results_basedir',
                        default='/tmp/testflinger/results'): str,
    voluptuous.Required('logging_level', default='INFO'): str,
    voluptuous.Required('logging_quiet', default=False): bool,
    voluptuous.Required('job_queues'): list,
    voluptuous.Required('setup_command', default=''): str,
    voluptuous.Required('provision_command', default=''): str,
    voluptuous.Required('test_command', default=''): str,
    voluptuous.Optional('global_timeout'): int,
    voluptuous.Optional('output_timeout'): int,
}


def validate(data):
    """Validate data according to known schemas

    :param data:
        Data to validate
    """
    v1 = voluptuous.Schema(SCHEMA_V1)
    return v1(data)
