# Copyright (C) 2016-2023 Canonical
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

from datetime import datetime
from io import BytesIO
import json
import os

from src.api import v1


def test_home(mongo_app):
    """Test that queries to / are redirected to /agents"""
    app, _ = mongo_app
    response = app.get("/")
    assert 302 == response.status_code
    assert "/agents" == response.headers.get("Location")


def test_add_job_good(mongo_app):
    """Test that adding a new job works"""
    job_data = {"job_queue": "test", "tags": ["foo", "bar"]}
    # Place a job on the queue
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    job_id = output.json.get("job_id")
    assert v1.check_valid_uuid(job_id)
    # Now get the job and confirm it matches
    output = app.get("/v1/job?queue=test")
    # Ensure everything we submitted is in the job_data we got back
    expected_data = set(job_data)
    actual_data = set(output.json)
    assert expected_data.issubset(actual_data)


def test_add_job_good_with_attachments(mongo_app, tmp_path):
    """Test that adding a new job with attachments works"""
    job_data = {
        "job_queue": "test",
        "test_data": {"attachments": [{"agent": "filename"}]},
    }
    # place a job on the queue
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    job_id = output.json.get("job_id")
    assert v1.check_valid_uuid(job_id)

    # confirm that the job cannot be processed yet (attachments pending)
    output = app.get("/v1/job?queue=test")
    assert 204 == output.status_code

    # create a mock attachments archive containing random data
    # (for the purpose of testing the server endpoints, the archive doesn't
    # need to match the attachments specified in the job)
    filename = tmp_path / "attachments.tar.gz"
    with open(filename, "wb") as attachments:
        attachments.write(os.urandom(8000))

    # submit the attachments archive for the job
    attachments_endpoint = f"/v1/job/{job_id}/attachments"
    with open(filename, "rb") as attachments:
        file_data = {"file": (attachments, filename.name)}
        output = app.post(
            attachments_endpoint,
            data=file_data,
            content_type="multipart/form-data",
        )
    assert 200 == output.status_code
    # check that the submitted attachments can be retrieved and
    # that they match the original data
    output = app.get(attachments_endpoint)
    with open(filename, "rb") as attachments:
        assert output.data == attachments.read()

    # ask for a job from the queue and confirm the match
    recovered_data = app.get("/v1/job?queue=test").json
    assert recovered_data["job_id"] == job_id
    assert set(job_data).issubset(recovered_data)


def test_submit_attachment_without_job(mongo_app, tmp_path):
    """Test for error when submitting attachments for a non-job"""
    app, _ = mongo_app
    nonexistent_id = "77777777-7777-7777-7777-777777777777"

    # create a mock attachments archive containing random data
    filename = tmp_path / "attachments.tar.gz"
    with open(filename, "wb") as attachments:
        attachments.write(os.urandom(8000))

    # submit the attachments archive for the job
    attachments_endpoint = f"/v1/job/{nonexistent_id}/attachments"
    with open(filename, "rb") as attachments:
        file_data = {"file": (attachments, filename.name)}
        output = app.post(
            attachments_endpoint,
            data=file_data,
            content_type="multipart/form-data",
        )
    assert 422 == output.status_code


def test_retrieve_attachments_nonexistent_job(mongo_app):
    """Test for error when requesting non-existent attachments"""
    app, _ = mongo_app
    nonexistent_id = "77777777-7777-7777-7777-777777777777"

    # request the attachments archive for the job
    attachments_endpoint = f"/v1/job/{nonexistent_id}/attachments"
    output = app.get(attachments_endpoint)
    assert 204 == output.status_code


def test_retrieve_attachments_nonexistent_attachment(mongo_app):
    """Test for error when requesting non-existent attachments"""
    job_data = {"job_queue": "test", "tags": ["foo", "bar"]}
    # place a job on the queue
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    job_id = output.json.get("job_id")
    assert v1.check_valid_uuid(job_id)

    # request the attachments archive for the job
    attachments_endpoint = f"/v1/job/{job_id}/attachments"
    output = app.get(attachments_endpoint)
    assert 204 == output.status_code


def test_add_job_good_with_jobid(mongo_app):
    """Test that adding a job with job ID works"""
    my_id = "77777777-7777-7777-7777-777777777777"
    job_data = {"job_id": my_id, "job_queue": "test"}
    # Place a job on the queue
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    job_id = output.json.get("job_id")
    assert my_id == job_id


def test_initial_job_state(mongo_app):
    """Ensure initial job state is set to 'waiting'"""
    app, _ = mongo_app
    job_data = {"job_queue": "test"}
    # Place a job on the queue
    output = app.post("/v1/job", json=job_data)
    job_id = output.json.get("job_id")
    result_url = "/v1/result/{}".format(job_id)
    response = app.get(result_url)
    assert "waiting" == response.json.get("job_state")


def test_resubmit_job_state(mongo_app):
    """Ensure initial job state is set to 'waiting'"""
    app, _ = mongo_app
    job_data = {"job_queue": "test"}
    # Place a job on the queue
    output = app.post("/v1/job", json=job_data)
    # insert the job_id into a job to resubmit
    job_id = output.json.get("job_id")
    job_data["job_id"] = job_id
    output = app.post("/v1/job", json=job_data)
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
    assert 422 == output.status_code


def test_add_job_bad_job_id(mongo_app):
    """Test for error when posting a job with a bad ID"""
    app, _ = mongo_app
    output = app.post("/v1/job", json={"job_id": "bad", "job_queue": "test"})
    assert "Invalid job_id specified" in output.text
    assert 400 == output.status_code


def test_add_job_bad_job_queue(mongo_app):
    """Test for error when adding a job without a queue"""
    app, _ = mongo_app
    output = app.post("/v1/job", json={"foo": "test"})
    assert "Validation error" in output.text
    assert 422 == output.status_code


def test_add_job_empty_queue(mongo_app):
    """Test for error when adding a job with an empty queue"""
    app, _ = mongo_app
    output = app.post("/v1/job", json={"job_queue": ""})
    assert "Invalid data or no job_queue specified" in output.text
    assert 422 == output.status_code


def test_result_get_result_not_exists(mongo_app):
    """Test for 204 when getting a nonexistent result"""
    app, _ = mongo_app
    output = app.get("/v1/result/11111111-1111-1111-1111-111111111111")
    assert 204 == output.status_code


def test_result_get_bad(mongo_app):
    """Test for error when getting results from a bad job ID"""
    app, _ = mongo_app
    output = app.get("/v1/result/BAD_JOB_ID")
    assert "Invalid job_id specified" in output.text
    assert 400 == output.status_code


def test_result_post_good(mongo_app):
    """Test that posting results correctly works"""
    app, _ = mongo_app
    newjob = app.post("/v1/job", json={"job_queue": "test"})
    job_id = newjob.json.get("job_id")
    result_url = f"/v1/result/{job_id}"
    data = {"test_output": "test output string"}
    response = app.post(result_url, json=data)
    assert "OK" == response.text
    response = app.get(result_url)
    assert response.json.get("test_output") == "test output string"


def test_result_post_bad(mongo_app):
    """Test for error when posting to a bad job ID"""
    app, _ = mongo_app
    response = app.post("/v1/result/BAD_JOB_ID")
    assert "Invalid job_id specified" in response.text
    assert 400 == response.status_code


def test_result_post_baddata(mongo_app):
    """Test that we get an error for posting results with no data"""
    app, _ = mongo_app
    result_url = "/v1/result/00000000-0000-0000-0000-000000000000"
    response = app.post(result_url, json={"foo": "bar"})
    assert "Validation error" in response.text
    assert 422 == response.status_code


def test_state_update_keeps_results(mongo_app):
    """Update job_state shouldn't lose old results"""
    app, _ = mongo_app
    newjob = app.post("/v1/job", json={"job_queue": "test"})
    job_id = newjob.json.get("job_id")
    result_url = f"/v1/result/{job_id}"
    data = {"setup_output": "test", "job_state": "waiting"}
    output = app.post(result_url, json=data)
    data = {"job_state": "provision"}
    output = app.post(result_url, json=data)
    output = app.get(result_url)
    current_results = output.json
    assert current_results.get("setup_output") == "test"


def test_artifact_post_good(mongo_app):
    """Test both get and put of a result artifact"""
    app, _ = mongo_app
    newjob = app.post("/v1/job", json={"job_queue": "test"})
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
    job_data = {"job_queue": "test", "provision_data": {"url": "test"}}
    # Place a job on the queue
    output = app.post("/v1/job", json=job_data)
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
        output = app.post("/v1/job", json=job_data)
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
    output = app.post(f"/v1/job/{job_id[1]}/action", json={"action": "cancel"})
    # The position of the remaining job should decrement again
    assert app.get("/v1/job/{}/position".format(job_id[2])).text == "0"


def test_action_post(mongo_app):
    """Test getting 422 code for an unsupported action"""
    app, _ = mongo_app
    action_url = "/v1/job/00000000-0000-0000-0000-000000000000/action"
    action_data = {"action": "foo"}
    output = app.post(action_url, json=action_data)
    assert 422 == output.status_code


def test_queues_post(mongo_app):
    """Test posting advertised queues"""
    app, _ = mongo_app
    queue_data = {"qfoo": "this is a test queue"}
    app.post("/v1/agents/queues", json=queue_data)
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
    app.post("/v1/agents/images", json=image_data)
    output = app.get("/v1/agents/images/myqueue")
    assert json.loads(output.data.decode()) == image_data.get("myqueue")


def test_get_invalid(mongo_app):
    """Get a nonexistent URL and confirm we get 404"""
    app, _ = mongo_app
    output = app.get("/v1/something")
    assert 404 == output.status_code


def test_cancel_job_completed(mongo_app):
    """Test that a job can't be cancelled if completed or cancelled already"""
    app, _ = mongo_app
    job_data = {"job_queue": "test"}
    job_output = app.post("/v1/job", json=job_data)
    job_id = job_output.json.get("job_id")
    result_url = f"/v1/result/{job_id}"

    # Set the job to cancelled and completed to ensure we get an error when
    # trying to cancel it in that state
    for state in ["cancelled", "complete", "completed"]:
        data = {"job_state": state}
        output = app.post(result_url, json=data)
        output = app.post(
            f"/v1/job/{job_id}/action", json={"action": "cancel"}
        )
        assert "The job is already completed or cancelled" == output.text
        assert 400 == output.status_code


def test_cancel_job_good(mongo_app):
    """Test if a valid job with waiting status can be cancelled"""
    app, mongo = mongo_app
    job_data = {"job_queue": "test"}
    job_output = app.post("/v1/job", json=job_data)
    job_id = job_output.json.get("job_id")

    # Make sure the job exists
    job = mongo.jobs.find_one({"job_id": job_id})
    assert job is not None
    assert job["result_data"]["job_state"] == "waiting"

    # Cancel the job
    output = app.post(f"/v1/job/{job_id}/action", json={"action": "cancel"})
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
    output = app.post(f"/v1/agents/data/{agent_name}", json=agent_data)

    assert 200 == output.status_code
    assert "OK" == output.text

    # Test that the expected data was stored
    agent_record = mongo.agents.find_one({"name": agent_name})
    assert agent_data.items() <= agent_record.items()

    # Update the agent data again
    output = app.post(f"/v1/agents/data/{agent_name}", json=agent_data)

    # Test that the log data was appended and truncated
    agent_record = mongo.agents.find_one({"name": agent_name})
    assert agent_record["log"] == (logdata + logdata)[-100:]


def test_agents_post_bad(mongo_app):
    """Test posting agent data with bad data"""
    app, _ = mongo_app
    agent_name = "agent1"
    agent_data = "BAD_DATA_SHOULD_BE_JSON"
    output = app.post(f"/v1/agents/data/{agent_name}", json=agent_data)

    assert 422 == output.status_code
    assert "Validation error" in output.text


def test_agents_provision_logs_post(mongo_app):
    """Test posting provision logs for an agent"""
    app, mongo = mongo_app
    agent_name = "agent1"
    provision_log = {
        "job_id": "00000000-0000-0000-0000-00000000000",
        "exit_code": 1,
        "detail": "provision_failed",
    }

    # Ensure that agent data for this agent exists
    agent_data = {"state": "waiting"}
    result = app.post(f"/v1/agents/data/{agent_name}", json=agent_data)
    assert 200 == result.status_code

    # Test that the post is successful
    result = app.post(
        f"/v1/agents/provision_logs/{agent_name}", json=provision_log
    )
    assert 200 == result.status_code
    assert "OK" == result.text

    # Test that the expected data was stored
    provision_log_records = mongo.provision_logs.find_one({"name": agent_name})
    assert (
        provision_log.items()
        <= provision_log_records["provision_log"][0].items()
    )

    # Test failed provision streak is reflected in the agent data
    agent_data = mongo.agents.find_one({"name": agent_name})
    assert agent_data["provision_streak_type"] == "fail"
    assert agent_data["provision_streak_count"] == 1

    # Now we should have two provision log entries
    provision_log["exit_code"] = 0
    app.post(f"/v1/agents/provision_logs/{agent_name}", json=provision_log)
    provision_log_records = mongo.provision_logs.find_one({"name": agent_name})
    assert len(provision_log_records["provision_log"]) == 2

    # Test that provision streak is now changed to pass
    agent_data = mongo.agents.find_one({"name": agent_name})
    assert agent_data["provision_streak_type"] == "pass"
    assert agent_data["provision_streak_count"] == 1


def test_agents_status_put(mongo_app, requests_mock):
    """Test api to receive agent status requests"""
    app, _ = mongo_app
    job_data = {"job_queue": "test"}
    job_output = app.post("/v1/job", json=job_data)
    job_id = job_output.json.get("job_id")

    webhook = "http://mywebhook.com"
    requests_mock.put(webhook, status_code=200, text="webhook requested")
    status_update_data = {
        "agent_id": "agent1",
        "job_queue": "myjobqueue",
        "job_status_webhook": webhook,
        "events": [
            {
                "event_name": "my_event",
                "timestamp": "2014-12-22T03:12:58.019077+00:00",
                "detail": "mymsg",
            }
        ],
    }
    output = app.post(f"/v1/job/{job_id}/events", json=status_update_data)
    assert 200 == output.status_code
    assert "webhook requested" == output.text


def test_get_agents_data(mongo_app):
    """Test api to retrieve agent data"""
    app, _ = mongo_app
    agent_name = "agent1"
    agent_data = {
        "state": "provision",
        "queues": ["q1", "q2"],
        "location": "here",
    }
    output = app.post(f"/v1/agents/data/{agent_name}", json=agent_data)
    assert 200 == output.status_code

    # Get the agent data
    output = app.get("/v1/agents/data")
    assert 200 == output.status_code
    assert len(output.json) == 1
    for key, value in agent_data.items():
        assert output.json[0][key] == value


def test_search_jobs_by_tags(mongo_app):
    """Test search_jobs by tags"""
    app, _ = mongo_app

    # Create some test jobs
    job1 = {
        "job_queue": "test",
        "tags": ["tag1", "tag2"],
    }
    job2 = {
        "job_queue": "test",
        "tags": ["tag2", "tag3"],
    }
    job3 = {
        "job_queue": "test",
        "tags": ["tag3", "tag4"],
    }
    app.post("/v1/job", json=job1)
    app.post("/v1/job", json=job2)
    app.post("/v1/job", json=job3)

    # Match any of the specified tags
    output = app.get("/v1/job/search?tags=tag1&tags=tag2")
    assert 200 == output.status_code
    assert len(output.json) == 2

    # Match all of the specified tags
    output = app.get("/v1/job/search?tags=tag2&tags=tag3&match=all")
    assert 200 == output.status_code
    assert len(output.json) == 1


def test_search_jobs_invalid_match(mongo_app):
    """Test search_jobs with invalid match"""
    app, _ = mongo_app

    output = app.get("/v1/job/search?match=foo")
    assert 422 == output.status_code
    assert "Must be one of" in output.text


def test_search_jobs_by_state(mongo_app):
    """Test search jobs by state"""
    app, _ = mongo_app

    job = {
        "job_queue": "test",
        "tags": ["foo"],
    }
    # Two jobs that will stay in waiting state
    app.post("/v1/job", json=job)
    app.post("/v1/job", json=job)

    # One job that will be cancelled
    job_response = app.post("/v1/job", json=job)
    job_id = job_response.json.get("job_id")
    result_url = f"/v1/result/{job_id}"
    data = {"job_state": "cancelled"}
    app.post(result_url, json=data)

    # One job that will be completed
    job_response = app.post("/v1/job", json=job)
    job_id = job_response.json.get("job_id")
    result_url = f"/v1/result/{job_id}"
    data = {"job_state": "completed"}
    app.post(result_url, json=data)

    # By default, all jobs are included if we don't specify the state
    output = app.get("/v1/job/search?tags=foo")
    assert 200 == output.status_code
    assert len(output.json) == 4

    # We can restrict this to active jobs
    output = app.get("/v1/job/search?tags=foo&state=active")
    assert 200 == output.status_code
    assert len(output.json) == 2

    # But we can specify searching for one in any state
    output = app.get("/v1/job/search?state=cancelled")
    assert 200 == output.status_code
    assert len(output.json) == 1


def test_search_jobs_invalid_state(mongo_app):
    """Test search jobs with invalid state"""
    app, _ = mongo_app

    output = app.get("/v1/job/search?state=foo")
    assert 422 == output.status_code
    assert "Must be one of" in output.text


def test_search_jobs_datetime_iso8601(mongo_app):
    """Test that the created_at field is returned in ISO8601 format"""
    app, mongo = mongo_app

    job = {
        "job_queue": "test",
        "tags": ["foo"],
    }
    job_response = app.post("/v1/job", json=job)
    job_id = job_response.json.get("job_id")
    mongo.jobs.update_one(
        {"job_id": job_id},
        {"$set": {"created_at": datetime(2020, 1, 1)}},
    )
    output = app.get("/v1/job/search?tags=foo")
    assert 200 == output.status_code
    assert output.json[0]["created_at"] == "2020-01-01T00:00:00Z"
