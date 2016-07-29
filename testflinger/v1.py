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


def home():
    """Identify ourselves"""
    return 'Testflinger Server'


def add_job():
    """Add a job to the queue"""
    return "OK"


def result_post(job_id):
    """Post a result for a specified job_id

    :param job_id:
        UUID as a string for the job
    """
    return "OK"


def result_get(job_id):
    """Return results for a specified job_id

    :param job_id:
        UUID as a string for the job
    :return:
        json data of results for the specified id
    """
    return "OK"
