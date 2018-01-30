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

import fakeredis
import json
import shutil
import tempfile
import testflinger
import pytest

from io import BytesIO


class TestAPI():
    @pytest.fixture
    def app(self):
        testflinger.app.config['DATA_PATH'] = tempfile.mkdtemp()
        yield testflinger.app.test_client()
        shutil.rmtree(testflinger.app.config['DATA_PATH'])

    def test_home(self, app):
        output = app.get('/')
        assert testflinger._get_version() == output.data.decode()

    def test_add_job_good(self, mocker, app):
        mocker.patch('redis.Redis', fakeredis.FakeRedis)
        job_data = json.dumps(dict(job_queue='test'))
        # Place a job on the queue
        output = app.post('/v1/job', data=job_data,
                          content_type='application/json')
        job_id = json.loads(output.data.decode()).get('job_id')
        assert testflinger.v1.check_valid_uuid(job_id)
        # Now get the job and confirm it matches
        output = app.get('/v1/job?queue=test')
        # unittest assertDictContainsSubset is deprecated, but
        # this works pretty well in its place
        expected_data = set(json.loads(job_data))
        actual_data = set(json.loads(output.data.decode()))
        assert expected_data.issubset(actual_data)

    def test_add_job_good_with_jobid(self, mocker, app):
        mocker.patch('redis.Redis', fakeredis.FakeRedis)
        my_id = '77777777-7777-7777-7777-777777777777'
        job_data = json.dumps(dict(job_id=my_id, job_queue='test'))
        # Place a job on the queue
        output = app.post('/v1/job', data=job_data,
                          content_type='application/json')
        job_id = json.loads(output.data.decode()).get('job_id')
        assert my_id == job_id

    def test_initial_job_state(self, mocker, app):
        """Ensure initial job state is set to 'waiting'"""
        mocker.patch('redis.Redis', fakeredis.FakeRedis)
        job_data = json.dumps(dict(job_queue='test'))
        # Place a job on the queue
        output = app.post('/v1/job', data=job_data,
                          content_type='application/json')
        job_id = json.loads(output.data.decode()).get('job_id')
        result_url = '/v1/result/{}'.format(job_id)
        updated_data = json.loads(app.get(result_url).data.decode())
        assert 'waiting' == updated_data.get('job_state')

    def test_resubmit_job_state(self, mocker, app):
        """Ensure initial job state is set to 'waiting'"""
        mocker.patch('redis.Redis', fakeredis.FakeRedis)
        job_data = dict(job_queue='test')
        # Place a job on the queue
        output = app.post('/v1/job', data=json.dumps(job_data),
                          content_type='application/json')
        # insert the job_id into a job to resubmit
        job_id = json.loads(output.data.decode()).get('job_id')
        job_data['job_id'] = job_id
        output = app.post('/v1/job', data=json.dumps(job_data),
                          content_type='application/json')
        result_url = '/v1/result/{}'.format(job_id)
        updated_data = json.loads(app.get(result_url).data.decode())
        assert 'resubmitted' == updated_data.get('job_state')

    def test_get_nonexistant_job(self, mocker, app):
        mocker.patch('redis.Redis', fakeredis.FakeRedis)
        output = app.get('/v1/job?queue=BAD_QUEUE_NAME')
        assert 204 == output.status_code

    def test_get_job_no_queue(self, app):
        output = app.get('/v1/job')
        assert 400 == output.status_code

    def test_add_job_bad(self, app):
        output = app.post('/v1/job')
        assert 400 == output.status_code

    def test_add_job_bad_job_id(self, app):
        output = app.post('/v1/job',
                          data=json.dumps(dict(job_id='bad',
                                               job_queue='test')),
                          content_type='application/json')
        assert 'Invalid job_id specified\n' == output.data.decode()
        assert 400 == output.status_code

    def test_add_job_bad_job_queue(self, app):
        output = app.post('/v1/job',
                          data=json.dumps(dict(foo='test')),
                          content_type='application/json')
        assert 'Invalid data or no job_queue specified\n' == \
            output.data.decode()
        assert 400 == output.status_code

    def test_result_get_result_not_exists(self, app):
        output = app.get(
            '/v1/result/11111111-1111-1111-1111-111111111111')
        assert 204 == output.status_code

    def test_result_get_bad(self, app):
        output = app.get('/v1/result/BAD_JOB_ID')
        assert 'Invalid job id\n' == output.data.decode()
        assert 400 == output.status_code

    def test_result_post_good(self, app):
        result_url = '/v1/result/00000000-0000-0000-0000-000000000000'
        data = json.dumps(dict(foo='test'))
        output = app.post(result_url, data=data,
                          content_type='application/json')
        assert 'OK' == output.data.decode()
        output = app.get(result_url)
        assert output.data.decode() == data

    def test_result_post_bad(self, app):
        output = app.post('/v1/result/BAD_JOB_ID')
        assert 'Invalid job id\n' == output.data.decode()
        assert 400 == output.status_code

    def test_artifact_post_good(self, app):
        """Test both get and put of a result artifact"""
        result_url = '/v1/result/00000000-0000-0000-0000-000000000000/artifact'
        data = b'test file content'
        filedata = dict(file=(BytesIO(data), 'artifact.tgz'))
        output = app.post(result_url, data=filedata,
                          content_type='multipart/form-data')
        assert 'OK' == output.data.decode()
        output = app.get(result_url)
        assert output.data == data

    def test_result_get_artifact_not_exists(self, app):
        output = app.get(
            '/v1/result/11111111-1111-1111-1111-111111111111/artifact')
        assert 204 == output.status_code

    def test_output_post_get(self, app):
        output_url = '/v1/result/00000000-0000-0000-0000-000000000000/output'
        data = 'line1\nline2\nline3'
        output = app.post(output_url, data=data)
        assert 'OK' == output.data.decode()
        output = app.get(output_url)
        assert output.data.decode() == data

    def test_job_get_id_invalid(self, app):
        job_url = '/v1/result/00000000-0000-0000-0000-00000000000X'
        output = app.get(job_url)
        assert 400 == output.status_code

    def test_job_get_id_no_data(self, app):
        job_url = '/v1/result/00000000-0000-0000-0000-000000000000'
        output = app.get(job_url)
        assert 204 == output.status_code
        assert '' == output.data.decode()

    def test_job_get_id_with_data(self, app):
        job_data = dict(job_queue='test', provision_data='test')
        # Place a job on the queue
        output = app.post('/v1/job', data=json.dumps(job_data),
                          content_type='application/json')
        job_id = json.loads(output.data.decode()).get('job_id')
        job_url = '/v1/job/{}'.format(job_id)
        # Request the original json for the job
        app.get(job_url)
        output = app.get(job_url)
        assert 200 == output.status_code
        # Inject the job_id into the expected job, since it will have that
        # added to it
        job_data['job_id'] = job_id
        assert output.data.decode() == json.dumps(job_data)
