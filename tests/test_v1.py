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

from io import BytesIO
from src.api import v1


def test_home(mongo_app):
    """Test that queries to / are redirected to /agents"""
    app, _ = mongo_app
    response = app.get("/")
    assert 302 == response.status_code
    assert "/agents" == response.headers.get("Location")


def test_add_job_good(mongo_app):
    """Test that adding a new job works"""
    job_data = json.dumps({"job_queue": "test"})
    # Place a job on the queue
    app, _ = mongo_app
    output = app.post(
        "/v1/job", data=job_data, content_type="application/json"
    )
    job_id = output.json.get("job_id")
    assert v1.check_valid_uuid(job_id)
    # Now get the job and confirm it matches
    output = app.get("/v1/job?queue=test")
    # Ensure everything we submitted is in the job_data we got back
    expected_data = set(json.loads(job_data))
    actual_data = set(output.json)
    assert expected_data.issubset(actual_data)


def test_add_job_good_with_jobid(mongo_app):
    """Test that adding a job with job ID works"""
    my_id = "77777777-7777-7777-7777-777777777777"
    job_data = json.dumps({"job_id": my_id, "job_queue": "test"})
    # Place a job on the queue
    app, _ = mongo_app
    output = app.post(
        "/v1/job", data=job_data, content_type="application/json"
    )
    job_id = output.json.get("job_id")
    assert my_id == job_id


def test_initial_job_state(mongo_app):
    """Ensure initial job state is set to 'waiting'"""
    app, _ = mongo_app
    job_data = json.dumps({"job_queue": "test"})
    # Place a job on the queue
    output = app.post(
        "/v1/job", data=job_data, content_type="application/json"
    )
    job_id = output.json.get("job_id")
    result_url = "/v1/result/{}".format(job_id)
    response = app.get(result_url)
    assert "waiting" == response.json.get("job_state")


def test_resubmit_job_state(mongo_app):
    """Ensure initial job state is set to 'waiting'"""
    app, _ = mongo_app
    job_data = {"job_queue": "test"}
    # Place a job on the queue
    output = app.post(
        "/v1/job", data=json.dumps(job_data), content_type="application/json"
    )
    # insert the job_id into a job to resubmit
    job_id = output.json.get("job_id")
    job_data["job_id"] = job_id
    output = app.post(
        "/v1/job", data=json.dumps(job_data), content_type="application/json"
    )
    result_url = "/v1/result/{}".format(job_id)
    updated_data = app.get(result_url).json
    assert "waiting" == updated_data.get("job_state")


def test_get_nonexistant_job(mongo_app):
    """Test for 204 when getting from a nonexistent queue"""
    app, _ = mongo_app
    output = app.get("/v1/job?queue=BAD_QUEUE_NAME")
    assert 204 == output.status_code


def test_get_job_no_queue(mongo_app):
    """Test for error when getting a job without the ID"""
    app, _ = mongo_app
    output = app.get("/v1/job")
    assert 400 == output.status_code


def test_add_job_bad(mongo_app):
    """Test for error when posting an empty job"""
    app, _ = mongo_app
    output = app.post("/v1/job", json={})
    assert 400 == output.status_code


def test_add_job_bad_job_id(mongo_app):
    """Test for error when posting a job with a bad ID"""
    app, _ = mongo_app
    output = app.post(
        "/v1/job",
        data=json.dumps({"job_id": "bad", "job_queue": "test"}),
        content_type="application/json",
    )
    assert "Invalid job_id specified\n" == output.text
    assert 400 == output.status_code


def test_add_job_bad_job_queue(mongo_app):
    """Test for error when adding a job without a queue"""
    app, _ = mongo_app
    output = app.post(
        "/v1/job",
        data=json.dumps({"foo": "test"}),
        content_type="application/json",
    )
    assert "Invalid data or no job_queue specified\n" == output.text
    assert 400 == output.status_code


def test_result_get_result_not_exists(mongo_app):
    """Test for 204 when getting a nonexistent result"""
    app, _ = mongo_app
    output = app.get("/v1/result/11111111-1111-1111-1111-111111111111")
    assert 204 == output.status_code


def test_result_get_bad(mongo_app):
    """Test for error when getting results from a bad job ID"""
    app, _ = mongo_app
    output = app.get("/v1/result/BAD_JOB_ID")
    assert "Invalid job id\n" == output.text
    assert 400 == output.status_code


def test_result_post_good(mongo_app):
    """Test that posting results correctly works"""
    app, _ = mongo_app
    newjob = app.post(
        "/v1/job",
        data=json.dumps({"job_queue": "test"}),
        content_type="application/json",
    )
    job_id = newjob.json.get("job_id")
    result_url = f"/v1/result/{job_id}"
    data = json.dumps({"test_output": "test output string"})
    response = app.post(result_url, data=data, content_type="application/json")
    assert "OK" == response.text
    response = app.get(result_url)
    assert response.json.get("test_output") == "test output string"


def test_result_post_bad(mongo_app):
    """Test for error when posting to a bad job ID"""
    app, _ = mongo_app
    response = app.post("/v1/result/BAD_JOB_ID")
    assert "Invalid job id\n" == response.text
    assert 400 == response.status_code


def test_result_post_nodata(mongo_app):
    """Test that we get an error for posting results with no data"""
    app, _ = mongo_app
    result_url = "/v1/result/00000000-0000-0000-0000-000000000000"
    response = app.post(result_url, data="", content_type="application/json")
    assert "Invalid result data\n" == response.text
    assert 400 == response.status_code


def test_state_update_keeps_results(mongo_app):
    """Update job_state shouldn't lose old results"""
    app, _ = mongo_app
    newjob = app.post(
        "/v1/job",
        data=json.dumps({"job_queue": "test"}),
        content_type="application/json",
    )
    job_id = newjob.json.get("job_id")
    result_url = f"/v1/result/{job_id}"
    data = json.dumps({"foo": "test", "job_state": "waiting"})
    output = app.post(result_url, data=data, content_type="application/json")
    data = json.dumps({"job_state": "provision"})
    output = app.post(result_url, data=data, content_type="application/json")
    output = app.get(result_url)
    current_results = output.json
    assert current_results.get("foo") == "test"


def test_artifact_post_good(mongo_app):
    """Test both get and put of a result artifact"""
    app, _ = mongo_app
    newjob = app.post(
        "/v1/job",
        data=json.dumps({"job_queue": "test"}),
        content_type="application/json",
    )
    job_id = newjob.json.get("job_id")
    artifact_url = f"/v1/result/{job_id}/artifact"
    data = b"test file content"
    filedata = {"file": (BytesIO(data), "artifact.tgz")}
    output = app.post(
        artifact_url, data=filedata, content_type="multipart/form-data"
    )
    assert "OK" == output.text
    output = app.get(artifact_url)
    assert output.data == data


def test_result_get_artifact_not_exists(mongo_app):
    """Get artifacts for a nonexistent job and confirm we get 204"""
    app, _ = mongo_app
    output = app.get(
        "/v1/result/11111111-1111-1111-1111-111111111111/artifact"
    )
    assert 204 == output.status_code


def test_output_post_get(mongo_app):
    """Test posting output data for a job then reading it back"""
    app, _ = mongo_app
    output_url = "/v1/result/00000000-0000-0000-0000-000000000000/output"
    data = "line1\nline2\nline3"
    output = app.post(output_url, data=data)
    assert "OK" == output.text
    output = app.get(output_url)
    assert output.text == data


def test_job_get_result_invalid(mongo_app):
    """Test getting results with bad job UUID fails"""
    app, _ = mongo_app
    job_url = "/v1/result/00000000-0000-0000-0000-00000000000X"
    output = app.get(job_url)
    assert 400 == output.status_code


def test_job_get_result_no_data(mongo_app):
    """Test getting results for a nonexistent job"""
    app, _ = mongo_app
    job_url = "/v1/result/00000000-0000-0000-0000-000000000000"
    output = app.get(job_url)
    assert 204 == output.status_code
    assert "" == output.text


def test_job_get_id_with_data(mongo_app):
    """Test getting the json for a job that has been submitted"""
    app, _ = mongo_app
    job_data = {"job_queue": "test", "provision_data": "test"}
    # Place a job on the queue
    output = app.post(
        "/v1/job", data=json.dumps(job_data), content_type="application/json"
    )
    job_id = output.json.get("job_id")
    job_url = "/v1/job/{}".format(job_id)
    # Request the original json for the job
    app.get(job_url)
    output = app.get(job_url)
    assert 200 == output.status_code
    # Inject the job_id into the expected job, since it will have that
    # added to it
    job_data["job_id"] = job_id
    assert output.json == job_data


def test_job_position(mongo_app):
    """Ensure initial job state is set to 'waiting'"""
    app, _ = mongo_app
    job_data = {"job_queue": "test"}
    # Place 3 jobs on the queue
    job_id = []
    for pos in range(3):
        output = app.post(
            "/v1/job",
            data=json.dumps(job_data),
            content_type="application/json",
        )
        job_id.append(output.json.get("job_id"))
        output = app.get("/v1/job/{}/position".format(job_id[pos]))
        # Initial position should increment for each job as we add them
        assert output.text == str(pos)

    # Request a job from the queue to remove one
    output = app.get("/v1/job?queue=test")
    # The job we get should be the first one that was added
    assert output.json.get("job_id") == job_id[0]
    # The position of the remaining jobs should decrement
    assert app.get("/v1/job/{}/position".format(job_id[2])).text == "1"
    # Cancel the next job in the queue
    output = app.post(
        f"/v1/job/{job_id[1]}/action", data=json.dumps({"action": "cancel"})
    )
    # The position of the remaining job should decrement again
    assert app.get("/v1/job/{}/position".format(job_id[2])).text == "0"


def test_action_post(mongo_app):
    """Test getting 400 code for an unsupported action"""
    app, _ = mongo_app
    action_url = "/v1/job/00000000-0000-0000-0000-000000000000/action"
    action_data = {"action": "foo"}
    output = app.post(action_url, data=json.dumps(action_data))
    assert 400 == output.status_code


def test_queues_post(mongo_app):
    """Test posting advertised queues"""
    app, _ = mongo_app
    queue_data = {"qfoo": "this is a test queue"}
    app.post(
        "/v1/agents/queues",
        data=json.dumps(queue_data),
        content_type="application/json",
    )
    output = app.get("/v1/agents/queues")
    assert output.json == queue_data


def test_images_post(mongo_app):
    """Test posting advertised images for a queue"""
    app, _ = mongo_app
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


def test_get_invalid(mongo_app):
    """Get a nonexistent URL and confirm we get 404"""
    app, _ = mongo_app
    output = app.get("/v1/something")
    assert 404 == output.status_code


def test_cancel_job_complete(mongo_app):
    """Test that a job can't be cancelled if complete or cancelled already"""
    app, _ = mongo_app
    job_data = json.dumps({"job_queue": "test"})
    job_output = app.post(
        "/v1/job", data=job_data, content_type="application/json"
    )
    job_id = job_output.json.get("job_id")
    result_url = f"/v1/result/{job_id}"

    # Set the job to cancelled and complete to ensure we get an error when
    # trying to cancel it in that state
    for state in ["cancelled", "complete"]:
        data = json.dumps({"job_state": state})
        output = app.post(
            result_url, data=data, content_type="application/json"
        )
        output = app.post(
            f"/v1/job/{job_id}/action", data=json.dumps({"action": "cancel"})
        )
        assert "The job is already complete or cancelled" == output.text
        assert 400 == output.status_code


def test_cancel_job_good(mongo_app):
    """Test if a valid job with waiting status can be cancelled"""
    app, mongo = mongo_app
    job_data = json.dumps({"job_queue": "test"})
    job_output = app.post(
        "/v1/job", data=job_data, content_type="application/json"
    )
    job_id = job_output.json.get("job_id")

    # Make sure the job exists
    job = mongo.jobs.find_one({"job_id": job_id})
    assert job is not None
    assert job["result_data"]["job_state"] == "waiting"

    # Cancel the job
    output = app.post(
        f"/v1/job/{job_id}/action", data=json.dumps({"action": "cancel"})
    )
    assert "OK" == output.text
    job = mongo.jobs.find_one({"job_id": job_id})
    assert job["result_data"]["job_state"] == "cancelled"


def test_agents_post(mongo_app):
    """Test posting agent data and updating it"""
    app, mongo = mongo_app
    agent_name = "agent1"
    logdata = [f"Log line {i}" for i in range(60)]
    agent_data = {
        "state": "provision",
        "queues": ["q1", "q2"],
        "location": "here",
        "log": logdata,
    }
    output = app.post(
        f"/v1/agents/data/{agent_name}",
        data=json.dumps(agent_data),
        content_type="application/json",
    )

    assert 200 == output.status_code
    assert "OK" == output.text

    # Test that the expected data was stored
    agent_record = mongo.agents.find_one({"name": agent_name})
    assert agent_data.items() <= agent_record.items()

    # Update the agent data again
    output = app.post(
        f"/v1/agents/data/{agent_name}",
        data=json.dumps(agent_data),
        content_type="application/json",
    )

    # Test that the log data was appended and truncated
    agent_record = mongo.agents.find_one({"name": agent_name})
    assert agent_record["log"] == (logdata + logdata)[-100:]


def test_agents_post_bad(mongo_app):
    """Test posting agent data with bad data"""
    app, _ = mongo_app
    agent_name = "agent1"
    agent_data = "BAD_DATA_SHOULD_BE_JSON"
    output = app.post(
        f"/v1/agents/data/{agent_name}",
        data=json.dumps(agent_data),
        content_type="application/json",
    )

    assert 400 == output.status_code
    assert "Invalid data\n" == output.text
