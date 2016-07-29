# Copyright (C) 2016 Canonical
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

import uuid

from flask import jsonify


def home():
    """Identify ourselves"""
    return 'Testflinger Server'


def add_job():
    """Add a job to the queue"""
    return jsonify(job_id=uuid.uuid1())


def result_post(job_id):
    """Post a result for a specified job_id

    :param job_id:
        UUID as a string for the job
    """
    if not check_valid_uuid(job_id):
        return 'Invalid job id\n', 400
    return "OK"


def result_get(job_id):
    """Return results for a specified job_id

    :param job_id:
        UUID as a string for the job
    :return:
        json data of results for the specified id
    """
    if not check_valid_uuid(job_id):
        return 'Invalid job id\n', 400
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
    except:
        return False
    return True
