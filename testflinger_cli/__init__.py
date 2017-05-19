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
import sys
import urllib.parse
import yaml


class HTTPError(Exception):
    def __init__(self, status):
        self.status = status


class Client():
    """Testflinger connection client"""
    def __init__(self, server):
        self.server = server

    def get(self, uri_frag, timeout=15):
        """Submit a GET request to the server
        :param uri_frag:
            endpoint for the GET request
        :return:
            String containing the response from the server
        """
        uri = urllib.parse.urljoin(self.server, uri_frag)
        try:
            req = requests.get(uri, timeout=timeout)
        except requests.exceptions.ConnectTimeout as e:
            print('Timeout while trying to communicate with the server.')
            raise
        except requests.exceptions.ConnectionError as e:
            print('Unable to communicate with specified server.')
            raise
        if req.status_code != 200:
            raise HTTPError(req.status_code)
        return req.text

    def put(self, uri_frag, data, timeout=15):
        """Submit a POST request to the server
        :param uri_frag:
            endpoint for the POST request
        :return:
            String containing the response from the server
        """
        uri = urllib.parse.urljoin(self.server, uri_frag)
        try:
            req = requests.post(uri, json=data, timeout=timeout)
        except requests.exceptions.ConnectTimeout as e:
            print('Timout while trying to communicate with the server.')
            sys.exit(1)
        except requests.exceptions.ConnectionError as e:
            print('Unable to communicate with specified server.')
            sys.exit(1)
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

    def submit_job(self, job_data):
        """Submit a test job to the testflinger server

        :param job_data:
            String containing json or yaml data for the job to submit
        :return:
            ID for the test job
        """
        endpoint = '/v1/job'
        data = yaml.load(job_data)
        response = self.put(endpoint, data)
        return json.loads(response).get('job_id')

    def show_job(self, job_id):
        """Show the JSON job definition for the specified ID

        :param job_id:
            ID for the test job
        :return:
            JSON job definition for the specified ID
        """
        endpoint = '/v1/job/{}'.format(job_id)
        return json.loads(self.get(endpoint))

    def get_results(self, job_id):
        """Get results for a specified test job

        :param job_id:
            ID for the test job
        :return:
            Dict containing the results returned from the server
        """
        endpoint = '/v1/result/{}'.format(job_id)
        return json.loads(self.get(endpoint))

    def get_artifact(self, job_id, path):
        """Get results for a specified test job

        :param job_id:
            ID for the test job
        :param path:
            Path and filename for the artifact file
        """
        endpoint = '/v1/result/{}/artifact'.format(job_id)
        uri = urllib.parse.urljoin(self.server, endpoint)
        req = requests.get(uri, timeout=15)
        if req.status_code != 200:
            raise HTTPError(req.status_code)
        with open(path, 'wb') as artifact:
            for chunk in req.iter_content(chunk_size=4096):
                artifact.write(chunk)

    def get_output(self, job_id):
        """Get the latest output for a specified test job

        :param job_id:
            ID for the test job
        :return:
            String containing the latest output from the job
        """
        endpoint = '/v1/result/{}/output'.format(job_id)
        return self.get(endpoint)
