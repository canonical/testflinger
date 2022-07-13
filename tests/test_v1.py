# Copyright (C) 2016-2022 Canonical
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
Unit tests for Testflinger v1 API
"""

import json
import shutil
import tempfile
import os

from io import BytesIO
import fakeredis
import pytest
import testflinger
from testflinger.api import v1


@pytest.fixture(name="app")
def fixture_app():
    """Create a pytest fixture for the app"""
    testflinger.app.config["DATA_PATH"] = tempfile.mkdtemp()
    testflinger.app.redis = fakeredis.FakeStrictRedis()
    yield testflinger.app.test_client()
    shutil.rmtree(testflinger.app.config["DATA_PATH"])


def test_home(app):
    """Test root URL returns the version"""
    output = app.get("/")
    assert testflinger.api.v1.get_version() == output.data.decode()


def test_add_job_good(app):
    """Test that adding a new job works"""
    job_data = json.dumps({"job_queue": "test"})
    # Place a job on the queue
    output = app.post(
        "/v1/job", data=job_data, content_type="application/json"
    )
    job_id = json.loads(output.data.decode()).get("job_id")
    assert v1.check_valid_uuid(job_id)
    # Ensure the queue will expire in about a week (604800s)
    assert 604000 < testflinger.app.redis.ttl("tf_queue_test") <= 604800
    # Now get the job and confirm it matches
    output = app.get("/v1/job?queue=test")
    # unittest assertDictContainsSubset is deprecated, but
    # this works pretty well in its place
    expected_data = set(json.loads(job_data))
    actual_data = set(json.loads(output.data.decode()))
    assert expected_data.issubset(actual_data)


def test_add_job_good_with_jobid(app):
    """Test that adding a job with job ID works"""
    my_id = "77777777-7777-7777-7777-777777777777"
    job_data = json.dumps({"job_id": my_id, "job_queue": "test"})
    # Place a job on the queue
    output = app.post(
        "/v1/job", data=job_data, content_type="application/json"
    )
    job_id = json.loads(output.data.decode()).get("job_id")
    assert my_id == job_id


def test_initial_job_state(app):
    """Ensure initial job state is set to 'waiting'"""
    job_data = json.dumps({"job_queue": "test"})
    # Place a job on the queue
    output = app.post(
        "/v1/job", data=job_data, content_type="application/json"
    )
    job_id = json.loads(output.data.decode()).get("job_id")
    result_url = "/v1/result/{}".format(job_id)
    updated_data = json.loads(app.get(result_url).data.decode())
    assert "waiting" == updated_data.get("job_state")


def test_resubmit_job_state(app):
    """Ensure initial job state is set to 'waiting'"""
    job_data = {"job_queue": "test"}
    # Place a job on the queue
    output = app.post(
        "/v1/job", data=json.dumps(job_data), content_type="application/json"
    )
    # insert the job_id into a job to resubmit
    job_id = json.loads(output.data.decode()).get("job_id")
    job_data["job_id"] = job_id
    output = app.post(
        "/v1/job", data=json.dumps(job_data), content_type="application/json"
    )
    result_url = "/v1/result/{}".format(job_id)
    updated_data = json.loads(app.get(result_url).data.decode())
    assert "resubmitted" == updated_data.get("job_state")


def test_get_nonexistant_job(app):
    """Test for 204 when getting from a nonexistent queue"""
    output = app.get("/v1/job?queue=BAD_QUEUE_NAME")
    assert 204 == output.status_code


def test_get_job_no_queue(app):
    """Test for error when getting a job without the ID"""
    output = app.get("/v1/job")
    assert 400 == output.status_code


def test_add_job_bad(app):
    """Test for error when posting an empty job"""
    output = app.post("/v1/job")
    assert 400 == output.status_code


def test_add_job_bad_job_id(app):
    """Test for error when posting a job with a bad ID"""
    output = app.post(
        "/v1/job",
        data=json.dumps({"job_id": "bad", "job_queue": "test"}),
        content_type="application/json",
    )
    assert "Invalid job_id specified\n" == output.data.decode()
    assert 400 == output.status_code


def test_add_job_bad_job_queue(app):
    """Test for error when adding a job without a queue"""
    output = app.post(
        "/v1/job",
        data=json.dumps({"foo": "test"}),
        content_type="application/json",
    )
    assert "Invalid data or no job_queue specified\n" == output.data.decode()
    assert 400 == output.status_code


def test_result_get_result_not_exists(app):
    """Test for 204 when getting a nonexistent result"""
    output = app.get("/v1/result/11111111-1111-1111-1111-111111111111")
    assert 204 == output.status_code


def test_result_get_bad(app):
    """Test for error when getting results from a bad job ID"""
    output = app.get("/v1/result/BAD_JOB_ID")
    assert "Invalid job id\n" == output.data.decode()
    assert 400 == output.status_code


def test_result_post_good(app):
    """Test that posting results correctly works"""
    result_url = "/v1/result/00000000-0000-0000-0000-000000000000"
    data = json.dumps({"foo": "test"})
    output = app.post(result_url, data=data, content_type="application/json")
    assert "OK" == output.data.decode()
    output = app.get(result_url)
    assert output.data.decode() == data


def test_result_post_bad(app):
    """Test for error when posting to a bad job ID"""
    output = app.post("/v1/result/BAD_JOB_ID")
    assert "Invalid job id\n" == output.data.decode()
    assert 400 == output.status_code


def test_result_post_nodata(app):
    """Test that we get an error for posting results with no data"""
    result_url = "/v1/result/00000000-0000-0000-0000-000000000000"
    output = app.post(result_url, data="", content_type="application/json")
    assert "Invalid result data\n" == output.data.decode()
    assert 400 == output.status_code


def test_state_update_keeps_results(app):
    """Update job_state shouldn't lose old results"""
    result_url = "/v1/result/00000000-0000-0000-0000-000000000000"
    data = json.dumps({"foo": "test", "job_state": "waiting"})
    output = app.post(result_url, data=data, content_type="application/json")
    data = json.dumps({"job_state": "provision"})
    output = app.post(result_url, data=data, content_type="application/json")
    output = app.get(result_url)
    current_results = json.loads(output.data.decode())
    assert current_results.get("foo") == "test"


def test_artifact_post_good(app):
    """Test both get and put of a result artifact"""
    result_url = "/v1/result/00000000-0000-0000-0000-000000000000/artifact"
    data = b"test file content"
    filedata = {"file": (BytesIO(data), "artifact.tgz")}
    output = app.post(
        result_url, data=filedata, content_type="multipart/form-data"
    )
    assert "OK" == output.data.decode()
    output = app.get(result_url)
    assert output.data == data


def test_result_get_artifact_not_exists(app):
    """Get artifacts for a nonexistent job and confirm we get 204"""
    output = app.get(
        "/v1/result/11111111-1111-1111-1111-111111111111/artifact"
    )
    assert 204 == output.status_code


def test_output_post_get(app):
    """Test posting output data for a job then reading it back"""
    output_url = "/v1/result/00000000-0000-0000-0000-000000000000/output"
    data = "line1\nline2\nline3"
    output = app.post(output_url, data=data)
    assert "OK" == output.data.decode()
    output = app.get(output_url)
    assert output.data.decode() == data


def test_job_get_result_invalid(app):
    """Test getting results with bad job UUID fails"""
    job_url = "/v1/result/00000000-0000-0000-0000-00000000000X"
    output = app.get(job_url)
    assert 400 == output.status_code


def test_job_get_result_no_data(app):
    """Test getting results for a nonexistent job"""
    job_url = "/v1/result/00000000-0000-0000-0000-000000000000"
    output = app.get(job_url)
    assert 204 == output.status_code
    assert "" == output.data.decode()


def test_job_get_id_with_data(app):
    """Test getting the json for a job that has been submitted"""
    job_data = {"job_queue": "test", "provision_data": "test"}
    # Place a job on the queue
    output = app.post(
        "/v1/job", data=json.dumps(job_data), content_type="application/json"
    )
    job_id = json.loads(output.data.decode()).get("job_id")
    job_url = "/v1/job/{}".format(job_id)
    # Request the original json for the job
    app.get(job_url)
    output = app.get(job_url)
    assert 200 == output.status_code
    # Inject the job_id into the expected job, since it will have that
    # added to it
    job_data["job_id"] = job_id
    assert output.data.decode() == json.dumps(job_data)


def test_job_position(app):
    """Ensure initial job state is set to 'waiting'"""
    job_data = {"job_queue": "test"}
    # Place a job on the queue
    for pos in range(3):
        output = app.post(
            "/v1/job",
            data=json.dumps(job_data),
            content_type="application/json",
        )
        job_id = json.loads(output.data.decode()).get("job_id")
        output = app.get("/v1/job/{}/position".format(job_id))
        print(output.data.decode())
        assert output.data.decode() == str(pos)


def test_action_post(app):
    """Test getting 400 code for an unsupported action"""
    action_url = "/v1/job/00000000-0000-0000-0000-000000000000/action"
    action_data = {"action": "foo"}
    output = app.post(action_url, data=json.dumps(action_data))
    assert 400 == output.status_code


def test_queues_post(app):
    """Test posting advertised queues"""
    queue_data = {"qfoo": "this is a test queue"}
    app.post(
        "/v1/agents/queues",
        data=json.dumps(queue_data),
        content_type="application/json",
    )
    output = app.get("/v1/agents/queues")
    assert json.loads(output.data.decode()) == queue_data


def test_images_post(app):
    """Test posting advertised images for a queue"""
    image_data = {
        "myqueue": {
            "image1": "url: http://path/to/image1",
            "image2": "url: http://path/to/image2",
        }
    }
    app.post(
        "/v1/agents/images",
        data=json.dumps(image_data),
        content_type="application/json",
    )
    output = app.get("/v1/agents/images/myqueue")
    assert json.loads(output.data.decode()) == image_data.get("myqueue")


def test_get_invalid(app):
    """Get a nonexistent URL and confirm we get 404"""
    output = app.get("/v1/something")
    assert 404 == output.status_code


def test_cancel_job_completed(app):
    """Test if a completed job cannot be cancelled"""
    my_id = "00000000-0000-0000-0000-000000000000"
    result_file = os.path.join(testflinger.app.config.get("DATA_PATH"), my_id)
    with open(result_file, "w+", encoding="utf-8") as results:
        results.write(json.dumps({"job_state": "complete"}))
    output = app.post(
        f"/v1/job/{my_id}/action", data=json.dumps({"action": "cancel"})
    )
    assert "The job is already completed or cancelled" == output.data.decode()
    assert 400 == output.status_code


def test_cancel_job_good(app):
    """Test if a valid job with waiting status can be cancelled"""
    job_data = json.dumps({"job_queue": "test"})
    job_output = app.post(
        "/v1/job", data=job_data, content_type="application/json"
    )
    job_id = json.loads(job_output.data.decode()).get("job_id")
    output = app.post(
        f"/v1/job/{job_id}/action", data=json.dumps({"action": "cancel"})
    )
    assert "OK" == output.data.decode()
    result_file = os.path.join(testflinger.app.config.get("DATA_PATH"), job_id)
    with open(result_file, "r", encoding="utf-8") as results:
        data = json.load(results)
    assert data["job_state"] == "cancelled"
