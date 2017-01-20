# Copyright (C) 2017 Canonical
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

import json
import requests
import urllib.parse


class HTTPError(Exception):
    def __init__(self, status):
        self.status = status


class Client():
    """Testflinger connection client"""
    def __init__(self, server):
        self.server = server

    def get(self, uri_frag):
        """Submit a GET request to the server
        :param uri_frag:
            endpoint for the GET request
        :return:
            String containing the response from the server
        """
        uri = urllib.parse.urljoin(self.server, uri_frag)
        req = requests.get(uri)
        if req.status_code != 200:
            raise HTTPError(req.status_code)
        return req.text

    def put(self, uri_frag, data):
        """Submit a POST request to the server
        :param uri_frag:
            endpoint for the POST request
        :return:
            String containing the response from the server
        """
        uri = urllib.parse.urljoin(self.server, uri_frag)
        req = requests.post(uri, json=data)
        if req.status_code != 200:
            raise HTTPError(req.status_code)
        return req.text

    def get_status(self, job_id):
        """Get the status of a test job

        :param job_id:
            ID for the test job
        :return:
            String containing the job_state for the specified ID
            (waiting, setup, provision, test, complete)
        """
        endpoint = '/v1/result/{}'.format(job_id)
        data = json.loads(self.get(endpoint))
        return data.get('job_state')

    def submit_job(self, json_data):
        """Submit a test job to the testflinger server

        :param json_data:
            String containing json data for the job to submit
        :return:
            ID for the test job
        """
        endpoint = '/v1/job'
        data = json.loads(json_data)
        response = self.put(endpoint, data)
        return json.loads(response).get('job_id')

    def get_results(self, job_id):
        """Get results for a specified test job

        :param job_id:
            ID for the test job
        :return:
            Dict containing the results returned from the server
        """
        endpoint = '/v1/result/{}'.format(job_id)
        return json.loads(self.get(endpoint))

    def get_output(self, job_id):
        """Get the latest output for a specified test job

        :param job_id:
            ID for the test job
        :return:
            String containing the latest output from the job
        """
        endpoint = '/v1/result/{}/output'.format(job_id)
        return self.get(endpoint)
