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
"""Unit tests for Testflinger v1 API."""

import json
import os
from datetime import datetime, timezone
from http import HTTPStatus

import pytest

from testflinger.api import v1


def test_home(mongo_app):
    """Test that queries to / are redirected to /agents."""
    app, _ = mongo_app
    response = app.get("/")
    assert 302 == response.status_code
    assert "/agents" == response.headers.get("Location")


def test_add_job_invalid_reserve_data(mongo_app):
    """Test that a job with an invalid reserve_data field fails."""
    # Invalid ssh_keys field
    job_data = {
        "job_queue": "test",
        "reserve_data": {"ssh_keys": {"lp": "me"}},
    }
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    assert 422 == output.status_code
    # Invalid multiple ssh_keys
    job_data = {
        "job_queue": "test",
        "reserve_data": {"ssh_keys": ["lp:me", {"gh": "alsome"}]},
    }
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    assert 422 == output.status_code
    # Unsupported SSH key server field
    job_data = {
        "job_queue": "test",
        "reserve_data": {"ssh_keys": ["who:me"]},
    }
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    assert 422 == output.status_code
    # Invalid timeout
    job_data = {
        "job_queue": "test",
        "reserve_data": {"timeout": "invalid"},
    }
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    assert 422 == output.status_code
    # Invalid additional fields
    job_data = {
        "job_queue": "test",
        "reserve_data": {"invalid_field": "what am I doing here"},
    }
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    assert 422 == output.status_code


def test_add_job_valid_reserve_data(mongo_app):
    """Test that a job with valid reserve_data field works."""
    # Valid ssh_keys
    job_data = {
        "job_queue": "test",
        "reserve_data": {"ssh_keys": ["lp:me"]},
    }
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    assert 200 == output.status_code
    # Valid multiple ssh_keys
    job_data = {
        "job_queue": "test",
        "reserve_data": {"ssh_keys": ["lp:me", "gh:alsome"]},
    }
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    assert 200 == output.status_code
    # Valid timeout
    job_data = {
        "job_queue": "test",
        "reserve_data": {"timeout": 1200},
    }
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    assert 200 == output.status_code
    # All reserve_data fields defined
    job_data = {
        "job_queue": "test",
        "reserve_data": {"ssh_keys": ["lp:me"], "timeout": 1200},
    }
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    assert 200 == output.status_code


def test_add_job_noprovision_provision_data(mongo_app):
    """Test that a job with noprovision provision_data works."""
    app, _ = mongo_app
    # Test with blank provision_data
    job_data = {"job_queue": "test", "provision_data": None}
    output = app.post("/v1/job", json=job_data)
    assert HTTPStatus.OK == output.status_code
    # Note: agents must register before they can be issued work:
    app.post(
        "/v1/agents/data/agent1",
        json={"state": "waiting", "queues": ["test"], "location": "here"},
    )
    recovered_data = app.get("/v1/job?queue=test").json
    assert recovered_data["provision_data"] is None
    # Test with provision_data skip=True
    provision_data = {"skip": True}
    job_data = {"job_queue": "test", "provision_data": provision_data}
    output = app.post("/v1/job", json=job_data)
    assert HTTPStatus.OK == output.status_code
    recovered_data = app.get("/v1/job?queue=test").json
    assert recovered_data["provision_data"] == provision_data
    # Test with provision_data skip=False
    provision_data = {"skip": False}
    job_data = {"job_queue": "test", "provision_data": provision_data}
    output = app.post("/v1/job", json=job_data)
    assert HTTPStatus.OK == output.status_code
    recovered_data = app.get("/v1/job?queue=test").json
    assert recovered_data["provision_data"] == provision_data


def test_add_job_cm3_provision_data(mongo_app):
    """Test that a job with cm3 provision_data works."""
    # Invalid URL fails
    provision_data = {"url": "invalid"}
    job_data = {"job_queue": "test", "provision_data": provision_data}
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    assert HTTPStatus.UNPROCESSABLE_ENTITY == output.status_code
    # Valid URL works
    provision_data = {"url": "http://example.com/image.img.xz"}
    job_data = {"job_queue": "test", "provision_data": provision_data}
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    assert HTTPStatus.OK == output.status_code


def test_add_job_maas_provision_data(mongo_app):
    """Test that a job with maas provision_data works."""
    # Empty provision_data works
    provision_data = {}
    job_data = {"job_queue": "test", "provision_data": provision_data}
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    assert HTTPStatus.OK == output.status_code
    # distro field works
    provision_data = {"distro": "noble"}
    job_data = {"job_queue": "test", "provision_data": provision_data}
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    assert HTTPStatus.OK == output.status_code
    # kernel field works
    provision_data = {"kernel": "test"}
    job_data = {"job_queue": "test", "provision_data": provision_data}
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    assert HTTPStatus.OK == output.status_code
    # user_data field works
    provision_data = {
        "kernel": "#cloud-config\npackages:\n- python3-pip\n- jq"
    }
    job_data = {"job_queue": "test", "provision_data": provision_data}
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    assert HTTPStatus.OK == output.status_code
    # disks field works
    provision_data = {
        "disks": [
            {"id": "disk0", "disk": 0, "type": "disk", "ptable": "gpt"},
            {
                "id": "disk0-part1",
                "device": "disk0",
                "type": "partition",
                "number": 1,
                "size": "2G",
                "alloc_pct": 80,
            },
            {
                "id": "disk0-part1-format",
                "type": "format",
                "volume": "disk0-part1",
                "fstype": "ext4",
                "label": "nova-ephemeral",
            },
            {
                "id": "disk0-part1-mount",
                "device": "disk0-part1-format",
                "path": "/",
                "type": "mount",
            },
        ],
    }
    job_data = {"job_queue": "test", "provision_data": provision_data}
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    assert HTTPStatus.OK == output.status_code


def test_add_job_multi_provision_data(mongo_app):
    """Test that a job with multi provision_data works."""
    # Empty jobs fails
    provision_data = {"jobs": []}
    job_data = {"job_queue": "test", "provision_data": provision_data}
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    assert HTTPStatus.UNPROCESSABLE_ENTITY == output.status_code
    # [TODO] Once jobs nested schema is defined, add validation here


def test_add_job_muxpi_provision_data(mongo_app):
    """Test that a job with muxpi provision_data works."""
    # Either url or use_attachment required
    provision_data = {"url": "", "use_attachment": "", "create_user": False}
    job_data = {"job_queue": "test", "provision_data": provision_data}
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    assert HTTPStatus.UNPROCESSABLE_ENTITY == output.status_code
    # Valid URL works
    provision_data = {
        "url": "http://example.com/image.img.xz",
        "create_user": False,
    }
    job_data = {"job_queue": "test", "provision_data": provision_data}
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    assert HTTPStatus.OK == output.status_code


def test_add_job_oem_autoinstall_provision_data(mongo_app):
    """Test that a job with oem_autoinstall provision_data works."""
    # Invalid URL fails
    provision_data = {"url": "invalid", "token_file": "file"}
    job_data = {"job_queue": "test", "provision_data": provision_data}
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    assert HTTPStatus.UNPROCESSABLE_ENTITY == output.status_code
    # Attachments works
    provision_data = {
        "url": "http://example.com/image.img.xz",
        "token_file": "file",
        "attachments": [{"agent": "filename"}],
    }
    job_data = {"job_queue": "test", "provision_data": provision_data}
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    assert HTTPStatus.OK == output.status_code
    # Valid URL works
    provision_data = {
        "url": "http://example.com/image.img.xz",
        "token_file": "file",
    }
    job_data = {"job_queue": "test", "provision_data": provision_data}
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    assert HTTPStatus.OK == output.status_code


def test_add_job_oem_script_provision_data(mongo_app):
    """Test that a job with oem_script provision_data works."""
    # Invalid URL fails
    provision_data = {"url": "invalid"}
    job_data = {"job_queue": "test", "provision_data": provision_data}
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    assert HTTPStatus.UNPROCESSABLE_ENTITY == output.status_code
    # Valid URL fails
    provision_data = {"url": "http://example.com/image.img.xz"}
    job_data = {"job_queue": "test", "provision_data": provision_data}
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    assert HTTPStatus.OK == output.status_code


def test_add_job_zapper_iot_preset_provision_data(mongo_app):
    """Test that a job with zapper_iot_preset provision_data works."""
    # Empty URLs fails
    provision_data = {"urls": [], "preset": ""}
    job_data = {"job_queue": "test", "provision_data": provision_data}
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    assert HTTPStatus.UNPROCESSABLE_ENTITY == output.status_code
    # Invalid URLs fails
    provision_data = {"urls": ["invalid"], "preset": ""}
    job_data = {"job_queue": "test", "provision_data": provision_data}
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    assert HTTPStatus.UNPROCESSABLE_ENTITY == output.status_code
    # Valid provision_data works
    provision_data = {
        "urls": ["http://example.com/image.img.xz"],
        "preset": "fake",
    }
    job_data = {"job_queue": "test", "provision_data": provision_data}
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    assert HTTPStatus.OK == output.status_code


def test_add_job_zapper_iot_custom_provision_data(mongo_app):
    """Test that a job with zapper_iot_custom provision_data works."""
    # Empty URLs fails
    provision_data = {
        "urls": [],
        "provision_plan": {},
        "ubuntu_sso_email": "test@example.com",
    }
    job_data = {"job_queue": "test", "provision_data": provision_data}
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    assert HTTPStatus.UNPROCESSABLE_ENTITY == output.status_code
    # [TODO] Add validation for provision_plan
    # Valid job works
    provision_data = {
        "urls": ["http://example.com/image.img.xz"],
        "provision_plan": {},
    }
    job_data = {"job_queue": "test", "provision_data": provision_data}
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    assert HTTPStatus.OK == output.status_code


def test_add_job_zapper_kvm_autoinstall_provision_data(mongo_app):
    """Test that a job with zapper_kvm_autoinstall provision_data works."""
    # Invalid URL fails
    provision_data = {
        "url": "invalid",
        "robot_tasks": ["task"],
        "autoinstall_storage_layout": "lvm",
    }
    job_data = {"job_queue": "test", "provision_data": provision_data}
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    assert HTTPStatus.UNPROCESSABLE_ENTITY == output.status_code
    # Valid provision_data works
    provision_data = {
        "url": "http://example.com/image.img.xz",
        "robot_tasks": ["task"],
        "autoinstall_storage_layout": "lvm",
    }
    job_data = {"job_queue": "test", "provision_data": provision_data}
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    assert HTTPStatus.OK == output.status_code


def test_add_job_zapper_kvm_oem_2204_provision_data(mongo_app):
    """Test that a job with zapper_kvm_oem_2204 provision_data works."""
    # Invalid URL fails
    provision_data = {
        "alloem_url": "invalid",
        "robot_tasks": ["task"],
    }
    job_data = {"job_queue": "test", "provision_data": provision_data}
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    assert HTTPStatus.UNPROCESSABLE_ENTITY == output.status_code
    # oem field works
    provision_data = {
        "alloem_url": "http://example.com/image.img.xz",
        "robot_tasks": ["task"],
        "oem": "dell",
    }
    job_data = {"job_queue": "test", "provision_data": provision_data}
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    assert HTTPStatus.OK == output.status_code


def test_add_job_zapper_kvm_generic_provision_data(mongo_app):
    """Test that a job with zapper_kvm_generic provision_data works."""
    # Invalid URL fails
    provision_data = {
        "url": "invalid",
        "robot_tasks": ["task"],
        "live_image": False,
        "wait_until_ssh": False,
    }
    job_data = {"job_queue": "test", "provision_data": provision_data}
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    assert HTTPStatus.UNPROCESSABLE_ENTITY == output.status_code
    # Valid provision_data works
    provision_data = {
        "url": "http://example.com/image.img.xz",
        "robot_tasks": ["task"],
        "live_image": False,
        "wait_until_ssh": False,
    }
    job_data = {"job_queue": "test", "provision_data": provision_data}
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    assert HTTPStatus.OK == output.status_code


def test_add_job_good(mongo_app):
    """Test that adding a new job works."""
    job_data = {"job_queue": "test", "tags": ["foo", "bar"]}
    # Place a job on the queue
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    job_id = output.json.get("job_id")
    assert v1.check_valid_uuid(job_id)
    # Note: agents must register before they can be issued work:
    app.post(
        "/v1/agents/data/agent1",
        json={"state": "waiting", "queues": ["test"], "location": "here"},
    )
    # Now get the job and confirm it matches
    output = app.get("/v1/job?queue=test")
    # Ensure everything we submitted is in the job_data we got back
    expected_data = set(job_data)
    actual_data = set(output.json)
    assert expected_data.issubset(actual_data)


def test_add_job_good_with_attachments(mongo_app, tmp_path):
    """Test that adding a new job with attachments works."""
    job_data = {
        "job_queue": "test",
        "test_data": {"attachments": [{"agent": "filename"}]},
    }
    # place a job on the queue
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    job_id = output.json.get("job_id")
    assert v1.check_valid_uuid(job_id)

    # Note: agents must register before they can be issued work:
    app.post(
        "/v1/agents/data/agent1",
        json={"state": "waiting", "queues": ["test"], "location": "here"},
    )

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
    """Test for error when submitting attachments for a non-job."""
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
    """Test for error when requesting non-existent attachments."""
    app, _ = mongo_app
    nonexistent_id = "77777777-7777-7777-7777-777777777777"

    # request the attachments archive for the job
    attachments_endpoint = f"/v1/job/{nonexistent_id}/attachments"
    output = app.get(attachments_endpoint)
    assert 204 == output.status_code


def test_retrieve_attachments_nonexistent_attachment(mongo_app):
    """Test for error when requesting non-existent attachments."""
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
    """Test that adding a job with job ID works."""
    my_id = "77777777-7777-7777-7777-777777777777"
    job_data = {"job_id": my_id, "job_queue": "test"}
    # Place a job on the queue
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    job_id = output.json.get("job_id")
    assert my_id == job_id


def test_initial_job_state(mongo_app):
    """Ensure initial job state is set to 'waiting'."""
    app, _ = mongo_app
    job_data = {"job_queue": "test"}
    # Place a job on the queue
    output = app.post("/v1/job", json=job_data)
    job_id = output.json.get("job_id")
    result_url = f"/v1/result/{job_id}"
    response = app.get(result_url)
    assert "waiting" == response.json.get("job_state")


def test_resubmit_job_state(mongo_app):
    """Ensure initial job state is set to 'waiting'."""
    app, _ = mongo_app
    job_data = {"job_queue": "test"}
    # Place a job on the queue
    output = app.post("/v1/job", json=job_data)
    # insert the job_id into a job to resubmit
    job_id = output.json.get("job_id")
    job_data["job_id"] = job_id
    output = app.post("/v1/job", json=job_data)
    result_url = f"/v1/result/{job_id}"
    updated_data = app.get(result_url).json
    assert "waiting" == updated_data.get("job_state")


def test_get_nonexistant_job(mongo_app):
    """Test for 204 when getting from a nonexistent queue."""
    app, _ = mongo_app
    # Note: agents must register before they can be issued work:
    app.post(
        "/v1/agents/data/agent1",
        json={"state": "waiting", "queues": ["test"], "location": "here"},
    )
    output = app.get("/v1/job?queue=BAD_QUEUE_NAME")
    assert 204 == output.status_code


def test_get_job_no_queue(mongo_app):
    """Test for error when getting a job without the ID."""
    app, _ = mongo_app
    output = app.get("/v1/job")
    assert 400 == output.status_code


def test_add_job_bad(mongo_app):
    """Test for error when posting an empty job."""
    app, _ = mongo_app
    output = app.post("/v1/job", json={})
    assert 422 == output.status_code


def test_add_job_bad_job_id(mongo_app):
    """Test for error when posting a job with a bad ID."""
    app, _ = mongo_app
    output = app.post("/v1/job", json={"job_id": "bad", "job_queue": "test"})
    assert "Invalid job_id specified" in output.text
    assert 400 == output.status_code


def test_add_job_bad_job_queue(mongo_app):
    """Test for error when adding a job without a queue."""
    app, _ = mongo_app
    output = app.post("/v1/job", json={"foo": "test"})
    assert "Validation error" in output.text
    assert 422 == output.status_code


def test_add_job_empty_queue(mongo_app):
    """Test for error when adding a job with an empty queue."""
    app, _ = mongo_app
    output = app.post("/v1/job", json={"job_queue": ""})
    assert "Invalid data or no job_queue specified" in output.text
    assert 422 == output.status_code


def test_job_get_id_with_data(mongo_app):
    """Test getting the json for a job that has been submitted."""
    app, _ = mongo_app
    job_data = {
        "job_queue": "test",
        "provision_data": {"url": "https://example.com/image.img.xz"},
    }
    # Place a job on the queue
    output = app.post("/v1/job", json=job_data)
    job_id = output.json.get("job_id")
    job_url = f"/v1/job/{job_id}"
    # Request the original json for the job
    app.get(job_url)
    output = app.get(job_url)
    assert 200 == output.status_code
    # Inject the job_id into the expected job, since it will have that
    # added to it
    job_data["job_id"] = job_id
    # The response may include exclude_agents field, verify submitted data
    for key, value in job_data.items():
        assert output.json[key] == value


def test_job_position(mongo_app):
    """Ensure initial job state is set to 'waiting'."""
    app, _ = mongo_app
    job_data = {"job_queue": "test"}
    # Place 3 jobs on the queue
    job_id = []
    for pos in range(3):
        output = app.post("/v1/job", json=job_data)
        job_id.append(output.json.get("job_id"))
        output = app.get(f"/v1/job/{job_id[pos]}/position")
        # Initial position should increment for each job as we add them
        assert output.text == str(pos)

    # Note: agents must register before they can be issued work:
    app.post(
        "/v1/agents/data/agent1",
        json={"state": "waiting", "queues": ["test"], "location": "here"},
    )

    # Request a job from the queue to remove one
    output = app.get("/v1/job?queue=test")
    # The job we get should be the first one that was added
    assert output.json.get("job_id") == job_id[0]
    # The position of the remaining jobs should decrement
    assert app.get(f"/v1/job/{job_id[2]}/position").text == "1"
    # Cancel the next job in the queue
    output = app.post(f"/v1/job/{job_id[1]}/action", json={"action": "cancel"})
    # The position of the remaining job should decrement again
    assert app.get(f"/v1/job/{job_id[2]}/position").text == "0"


def test_action_post(mongo_app):
    """Test getting 422 code for an unsupported action."""
    app, _ = mongo_app
    action_url = "/v1/job/00000000-0000-0000-0000-000000000000/action"
    action_data = {"action": "foo"}
    output = app.post(action_url, json=action_data)
    assert 422 == output.status_code


def test_queues_post(mongo_app):
    """Test posting advertised queues."""
    app, _ = mongo_app
    queue_data = {"qfoo": "this is a test queue"}
    app.post("/v1/agents/queues", json=queue_data)
    output = app.get("/v1/agents/queues")
    assert output.json == queue_data


def test_images_post(mongo_app):
    """Test posting advertised images for a queue."""
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
    """Get a nonexistent URL and confirm we get 404."""
    app, _ = mongo_app
    output = app.get("/v1/something")
    assert 404 == output.status_code


def test_cancel_job_completed(mongo_app):
    """Test that a job can't be cancelled if completed or cancelled already."""
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
    """Test if a valid job with waiting status can be cancelled."""
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
    """Test posting agent data and updating it."""
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
    assert "OK" == output.json.get("status")

    # Verify that agent_name cookie is set with correct attributes
    assert "Set-Cookie" in output.headers
    cookie_header = output.headers.get("Set-Cookie", "")
    assert "agent_name=" in cookie_header
    assert "HttpOnly" in cookie_header
    assert "SameSite=Strict" in cookie_header

    # Test that the expected data was stored
    agent_record = mongo.agents.find_one({"name": agent_name})
    assert agent_data.items() <= agent_record.items()

    # Update the agent data again
    output = app.post(f"/v1/agents/data/{agent_name}", json=agent_data)

    # Test that the log data was appended and truncated
    agent_record = mongo.agents.find_one({"name": agent_name})
    assert agent_record["log"] == (logdata + logdata)[-100:]


def test_agents_post_bad(mongo_app):
    """Test posting agent data with bad data."""
    app, _ = mongo_app
    agent_name = "agent1"
    agent_data = "BAD_DATA_SHOULD_BE_JSON"
    output = app.post(f"/v1/agents/data/{agent_name}", json=agent_data)

    assert 422 == output.status_code
    assert "Validation error" in output.text


def test_agents_provision_logs_post(mongo_app):
    """Test posting provision logs for an agent."""
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
    """Test api to receive agent status requests."""
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
    """Test api to retrieve agent data."""
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


def test_get_agents_data_single(mongo_app):
    """Test getting agent data from a specified agent."""
    app, _ = mongo_app
    agent_name1 = "agent1"
    agent_name2 = "agent2"
    agent_data1 = {
        "state": "provision",
        "queues": ["q1", "q2"],
        "location": "here",
    }
    agent_data2 = {
        "state": "waiting",
        "queues": ["q3", "q4"],
        "location": "here",
    }

    # Set the data for agent1
    output = app.post(f"/v1/agents/data/{agent_name1}", json=agent_data1)
    assert output.status_code == HTTPStatus.OK

    # Set the data for agent2
    output = app.post(f"/v1/agents/data/{agent_name2}", json=agent_data2)
    assert output.status_code == HTTPStatus.OK

    # Get the data from agent2
    output = app.get(f"/v1/agents/data/{agent_name2}")
    assert output.status_code == HTTPStatus.OK

    # Compare retrieved data with expected data
    assert all(output.json[key] == value for key, value in agent_data2.items())


def test_search_jobs_by_tags(mongo_app):
    """Test search_jobs by tags."""
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
    """Test search_jobs with invalid match."""
    app, _ = mongo_app

    output = app.get("/v1/job/search?match=foo")
    assert 422 == output.status_code
    assert "Must be one of" in output.text


def test_search_jobs_by_state(mongo_app):
    """Test search jobs by state."""
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
    """Test search jobs with invalid state."""
    app, _ = mongo_app

    output = app.get("/v1/job/search?state=foo")
    assert 422 == output.status_code
    assert "Must be one of" in output.text


def test_search_jobs_datetime_iso8601(mongo_app):
    """Test that the created_at field is returned in ISO8601 format."""
    app, mongo = mongo_app

    job = {
        "job_queue": "test",
        "tags": ["foo"],
    }
    job_response = app.post("/v1/job", json=job)
    job_id = job_response.json.get("job_id")
    mongo.jobs.update_one(
        {"job_id": job_id},
        {"$set": {"created_at": datetime(2020, 1, 1, tzinfo=timezone.utc)}},
    )
    output = app.get("/v1/job/search?tags=foo")
    assert 200 == output.status_code
    assert output.json[0]["created_at"] == "2020-01-01T00:00:00Z"


def test_get_queue_wait_times(mongo_app):
    """Test that the wait times for a queue are returned."""
    app, mongo = mongo_app

    # Add some fake wait times to the queue_wait_times collection
    mongo.queue_wait_times.insert_many(
        [
            {"name": "queue1", "wait_times": [1, 2, 3, 4, 5]},
            {"name": "queue2", "wait_times": [10, 20, 30, 40, 50]},
        ]
    )

    # Get the wait times for a specific queue
    output = app.get("/v1/queues/wait_times?queue=queue1")
    assert 200 == output.status_code
    assert len(output.json) == 1
    assert output.json["queue1"]["50"] == 3.0

    # Get the wait times for all queues
    output = app.get("/v1/queues/wait_times")
    assert 200 == output.status_code
    assert len(output.json) == 2
    assert output.json["queue1"]["50"] == 3.0
    assert output.json["queue2"]["50"] == 30.0


def test_get_agents_on_queue(mongo_app):
    """Test api to get agents on a queue."""
    app, _ = mongo_app
    agent_name = "agent1"
    agent_data = {"state": "provision", "queues": ["q1", "q2"]}
    output = app.post(f"/v1/agents/data/{agent_name}", json=agent_data)
    assert output.status_code == HTTPStatus.OK

    # Get the agents on the queue
    output = app.get("/v1/queues/q1/agents")
    assert output.status_code == HTTPStatus.OK
    assert len(output.json) == 1
    assert output.json[0]["name"] == agent_name

    # Should be aborted by the server if queue does not exist
    output = app.get("/v1/queues/q3/agents")
    assert output.status_code == HTTPStatus.NOT_FOUND
    assert "Queue 'q3' does not exist." in output.json["message"]


def test_agents_data_restricted_to(mongo_app):
    """Test restricted_to field in agents data."""
    app, mongo = mongo_app
    mongo.restricted_queues.insert_one({"queue_name": "q1"})

    mongo.client_permissions.insert_one(
        {
            "client_id": "test-client-id",
            "allowed_queues": ["q1"],
        }
    )

    agent_name = "agent1"
    agent_data = {
        "state": "provision",
        "queues": ["q1", "q2"],
        "location": "here",
    }

    output = app.post(f"/v1/agents/data/{agent_name}", json=agent_data)
    assert output.status_code == HTTPStatus.OK

    output = app.get("/v1/agents/data")
    assert output.status_code == HTTPStatus.OK

    result = output.json[0]
    expected_restricted_to = {
        "q1": ["test-client-id"],
    }
    assert result["restricted_to"] == expected_restricted_to


def test_get_jobs_on_queue(mongo_app):
    """Test api to get jobs on a queue."""
    app, _ = mongo_app
    job = {
        "job_queue": "test",
        "tags": ["foo"],
    }
    # Two jobs that will stay in waiting state
    app.post("/v1/job", json=job)
    app.post("/v1/job", json=job)

    # Validate the number of jobs on the queue is accurate
    output = app.get("/v1/queues/test/jobs")
    assert output.status_code == HTTPStatus.OK
    assert len(output.json) == 2

    # Confirm  the status code returned if there are no jobs in queue
    output = app.get("/v1/queues/test2/jobs")
    assert output.status_code == HTTPStatus.NO_CONTENT


@pytest.mark.parametrize("timeout", [1800, "1800", "30m", "1800s"])
def test_reserve_data_with_human_readable_timeout(mongo_app, timeout):
    """Test that a job with valid human readable timeout field works."""
    job_data = {
        "job_queue": "test",
        "reserve_data": {"timeout": timeout},
    }
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    assert output.status_code == HTTPStatus.OK
    # Note: agents must register before they can be issued work:
    app.post(
        "/v1/agents/data/agent1",
        json={"state": "waiting", "queues": ["test"], "location": "here"},
    )
    submitted_job = app.get("/v1/job?queue=test").json
    assert submitted_job["reserve_data"]["timeout"] == 1800


@pytest.mark.parametrize("timeout", ["invalid", "30x", "-30m", ""])
def test_reserve_data_with_invalid_timeout(mongo_app, timeout):
    """Test that a job with invalid timeout field is rejected."""
    job_data = {
        "job_queue": "test",
        "reserve_data": {"timeout": timeout},
    }
    app, _ = mongo_app
    output = app.post("/v1/job", json=job_data)
    assert output.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_job_post_exclude_agents_empty(mongo_app):
    """Test that a job with an empty exclude_agents list works."""
    app, mongo = mongo_app
    # Setup agents on the queue
    mongo.agents.insert_many(
        [
            {"name": "agent1", "queues": ["test"]},
            {"name": "agent2", "queues": ["test"]},
        ]
    )

    job_data = {
        "job_queue": "test",
        "exclude_agents": [],
    }
    output = app.post("/v1/job", json=job_data)
    assert output.status_code == HTTPStatus.OK
    assert output.json.get("job_id")


def test_job_post_exclude_agents_valid(mongo_app):
    """Test that a job with valid exclude_agents field works."""
    app, mongo = mongo_app
    # Setup agents on the queue
    mongo.agents.insert_many(
        [
            {"name": "agent1", "queues": ["test"]},
            {"name": "agent2", "queues": ["test"]},
        ]
    )

    job_data = {
        "job_queue": "test",
        "exclude_agents": ["agent1"],
    }
    output = app.post("/v1/job", json=job_data)
    assert output.status_code == HTTPStatus.OK
    assert output.json.get("job_id")


def test_job_post_without_exclude_agents(mongo_app):
    """Test job without exclude_agents field works (backward compatibility)."""
    app, mongo = mongo_app
    # Setup agents on the queue
    mongo.agents.insert_many(
        [
            {"name": "agent1", "queues": ["test"]},
            {"name": "agent2", "queues": ["test"]},
        ]
    )

    # Submit job without exclude_agents field at all
    job_data = {
        "job_queue": "test",
    }
    output = app.post("/v1/job", json=job_data)
    assert output.status_code == HTTPStatus.OK
    job_id = output.json.get("job_id")
    assert job_id

    # Verify job was created with default empty exclude_agents
    mongo_job = mongo.jobs.find_one({"job_id": job_id})
    assert "exclude_agents" in mongo_job["job_data"]
    assert mongo_job["job_data"]["exclude_agents"] == []


def test_job_post_exclude_agents_not_list(mongo_app):
    """Test that exclude_agents must be a list."""
    app, mongo = mongo_app
    mongo.agents.insert_one({"name": "agent1", "queues": ["test"]})

    job_data = {
        "job_queue": "test",
        "exclude_agents": "agent1",  # Invalid: should be a list
    }
    output = app.post("/v1/job", json=job_data)
    assert output.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    msg = output.json.get("message", "").lower()
    assert "must be a list" in msg or "list" in str(output.json).lower()


def test_job_post_exclude_agents_all_excluded(mongo_app):
    """Test that job submission fails if all agents are excluded."""
    app, mongo = mongo_app
    mongo.agents.insert_many(
        [
            {"name": "agent1", "queues": ["test"]},
            {"name": "agent2", "queues": ["test"]},
        ]
    )

    job_data = {
        "job_queue": "test",
        "exclude_agents": ["agent1", "agent2"],
    }
    output = app.post("/v1/job", json=job_data)
    assert output.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    msg = output.json.get("message", "").lower()
    assert "no agents" in msg or "agent" in str(output.json).lower()


def test_pop_job_respects_exclude_agents(mongo_app):
    """Test that pop_job filters excluded agents correctly."""
    app, mongo = mongo_app

    # Setup agents in database (there must be available agents to post jobs).
    mongo.agents.insert_many(
        [
            {"name": "agent1", "queues": ["test"]},
            {"name": "agent2", "queues": ["test"]},
        ]
    )

    # Submit a job that excludes agent1
    job_data = {"job_queue": "test", "exclude_agents": ["agent1"]}
    resp = app.post("/v1/job", json=job_data)
    assert resp.status_code == HTTPStatus.OK
    job_id = resp.json["job_id"]

    # Register as agent1 - should NOT get the job (204 No Content)
    app.post(
        "/v1/agents/data/agent1",
        json={"state": "waiting", "queues": ["test"], "location": "here"},
    )
    output = app.get("/v1/job?queue=test")
    assert output.status_code == HTTPStatus.NO_CONTENT

    # Register as agent2 - should get the job
    app.post(
        "/v1/agents/data/agent2",
        json={"state": "waiting", "queues": ["test"], "location": "here"},
    )
    output = app.get("/v1/job?queue=test")
    assert output.status_code == HTTPStatus.OK
    assert output.json["job_id"] == job_id


def test_get_job_without_agent_id_fails(mongo_app):
    """Test that getting a job without agent_id cookie fails."""
    app, mongo = mongo_app

    # Create a job
    job_data = {"job_queue": "test"}
    app.post("/v1/job", json=job_data)

    # Try to get job without agent_id (test client won't have cookie)
    # Make a raw request without any cookies
    with app.application.test_client() as raw_client:
        output = raw_client.get("/v1/job?queue=test")
        assert output.status_code == HTTPStatus.UNAUTHORIZED
