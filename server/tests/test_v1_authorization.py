# Copyright (C) 2024 Canonical
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
Unit tests for Testflinger v1 API relating to job priority and
restricted queues.
"""

import base64
import os
from datetime import datetime, timedelta, timezone
from http import HTTPStatus

import jwt

from testflinger.enums import ServerRoles


def create_auth_header(client_id: str, client_key: str) -> dict:
    """
    Create authorization header with base64 encoded client_id
    and client key using the Basic scheme.
    """
    id_key_pair = f"{client_id}:{client_key}"
    base64_encoded_pair = base64.b64encode(id_key_pair.encode("utf-8")).decode(
        "utf-8"
    )
    return {"Authorization": f"Basic {base64_encoded_pair}"}


def get_access_token(app, client_id, client_key):
    """Authenticate and return a valid access token."""
    response = app.post(
        "/v1/oauth2/token",
        headers=create_auth_header(client_id, client_key),
    )

    assert response.status_code == 200

    return response.get_json()["access_token"]


def test_retrieve_token(mongo_app_with_permissions):
    """Tests authentication endpoint which returns JWT with permissions."""
    app, _, client_id, client_key, max_priority = mongo_app_with_permissions
    token = get_access_token(app, client_id, client_key)

    decoded_token = jwt.decode(
        token,
        os.environ.get("JWT_SIGNING_KEY"),
        algorithms="HS256",
        options={"require": ["exp", "iat", "sub", "permissions"]},
    )

    assert decoded_token["permissions"]["max_priority"] == max_priority


def test_retrieve_token_invalid_client_id(mongo_app_with_permissions):
    """
    Tests that authentication endpoint returns 401 error code
    when receiving invalid client key.
    """
    app, _, _, client_key, _ = mongo_app_with_permissions
    client_id = "my_wrong_id"

    output = app.post(
        "/v1/oauth2/token",
        headers=create_auth_header(client_id, client_key),
    )

    assert output.status_code == 401


def test_retrieve_token_invalid_client_key(mongo_app_with_permissions):
    """
    Tests that authentication endpoint returns 401 error code
    when receiving invalid client key.
    """
    app, _, client_id, _, _ = mongo_app_with_permissions
    client_key = "my_wrong_key"

    output = app.post(
        "/v1/oauth2/token",
        headers=create_auth_header(client_id, client_key),
    )

    assert output.status_code == 401


def test_job_with_priority(mongo_app_with_permissions):
    """Tests submission of priority job with valid token."""
    app, _, client_id, client_key, _ = mongo_app_with_permissions
    token = get_access_token(app, client_id, client_key)

    job = {"job_queue": "myqueue2", "job_priority": 200}
    job_response = app.post(
        "/v1/job", json=job, headers={"Authorization": token}
    )

    assert 200 == job_response.status_code


def test_star_priority(mongo_app_with_permissions):
    """
    Tests submission of priority job for a generic queue
    with star priority permissions.
    """
    app, _, client_id, client_key, _ = mongo_app_with_permissions
    token = get_access_token(app, client_id, client_key)

    job = {"job_queue": "mygenericqueue", "job_priority": 1}
    job_response = app.post(
        "/v1/job", json=job, headers={"Authorization": token}
    )

    assert 200 == job_response.status_code


def test_priority_no_token(mongo_app_with_permissions):
    """Tests rejection of priority job with no token."""
    app, _, _, _, _ = mongo_app_with_permissions
    job = {"job_queue": "myqueue2", "job_priority": 200}
    job_response = app.post("/v1/job", json=job)
    assert job_response.status_code == HTTPStatus.UNAUTHORIZED
    message = job_response.get_json()["message"]
    assert "Authentication required for setting priority" in message


def test_priority_invalid_queue(mongo_app_with_permissions):
    """Tests rejection of priority job with invalid queue."""
    app, _, client_id, client_key, _ = mongo_app_with_permissions
    token = get_access_token(app, client_id, client_key)

    job = {"job_queue": "myinvalidqueue", "job_priority": 200}
    job_response = app.post(
        "/v1/job", json=job, headers={"Authorization": token}
    )

    assert 403 == job_response.status_code


def test_priority_expired_token(mongo_app_with_permissions):
    """Tests rejection of priority job with expired token."""
    app, _, _, _, _ = mongo_app_with_permissions
    secret_key = os.environ.get("JWT_SIGNING_KEY")
    expired_token_payload = {
        "exp": datetime.now(timezone.utc) - timedelta(seconds=2),
        "iat": datetime.now(timezone.utc) - timedelta(seconds=4),
        "sub": "access_token",
        "permissions": {
            "max_priority": {},
        },
    }
    token = jwt.encode(expired_token_payload, secret_key, algorithm="HS256")
    job = {"job_queue": "myqueue", "job_priority": 100}
    job_response = app.post(
        "/v1/job", json=job, headers={"Authorization": token}
    )
    assert 401 == job_response.status_code
    assert "Token has expired" in job_response.text


def test_missing_fields_in_token(mongo_app_with_permissions):
    """Tests rejection of priority job with token with missing fields."""
    app, _, _, _, _ = mongo_app_with_permissions
    secret_key = os.environ.get("JWT_SIGNING_KEY")
    incomplete_token_payload = {
        "permissions": {
            "max_priority": {},
        }
    }
    token = jwt.encode(incomplete_token_payload, secret_key, algorithm="HS256")
    job = {"job_queue": "myqueue", "job_priority": 100}
    job_response = app.post(
        "/v1/job", json=job, headers={"Authorization": token}
    )
    assert 403 == job_response.status_code
    assert "Invalid Token" in job_response.text


def test_job_get_with_priority(mongo_app_with_permissions):
    """Tests job get returns job with highest job priority."""
    app, _, client_id, client_key, _ = mongo_app_with_permissions
    token = get_access_token(app, client_id, client_key)

    jobs = [
        {"job_queue": "myqueue2"},
        {"job_queue": "myqueue2", "job_priority": 200},
        {"job_queue": "myqueue2", "job_priority": 100},
    ]

    job_ids = []
    for job in jobs:
        job_response = app.post(
            "/v1/job", json=job, headers={"Authorization": token}
        )
        job_id = job_response.json.get("job_id")
        job_ids.append(job_id)

    returned_job_ids = []
    for _ in range(len(jobs)):
        job_get_response = app.get("/v1/job?queue=myqueue2")
        job_id = job_get_response.json.get("job_id")
        returned_job_ids.append(job_id)

    assert returned_job_ids[0] == job_ids[1]
    assert returned_job_ids[1] == job_ids[2]
    assert returned_job_ids[2] == job_ids[0]


def test_job_get_with_priority_multiple_queues(mongo_app_with_permissions):
    """
    Tests job get returns job with highest job priority when jobs are
    submitted across different queues.
    """
    app, _, client_id, client_key, _ = mongo_app_with_permissions
    token = get_access_token(app, client_id, client_key)

    jobs = [
        {"job_queue": "myqueue3"},
        {"job_queue": "myqueue2", "job_priority": 200},
        {"job_queue": "myqueue", "job_priority": 100},
    ]

    job_ids = []
    for job in jobs:
        job_response = app.post(
            "/v1/job", json=job, headers={"Authorization": token}
        )
        job_id = job_response.json.get("job_id")
        job_ids.append(job_id)

    returned_job_ids = []
    for _ in range(len(jobs)):
        job_get_response = app.get(
            "/v1/job?queue=myqueue&queue=myqueue2&queue=myqueue3"
        )
        job_id = job_get_response.json.get("job_id")
        returned_job_ids.append(job_id)

    assert returned_job_ids[0] == job_ids[1]
    assert returned_job_ids[1] == job_ids[2]
    assert returned_job_ids[2] == job_ids[0]


def test_job_position_get_with_priority(mongo_app_with_permissions):
    """Tests job position get returns correct position with priority."""
    app, _, client_id, client_key, _ = mongo_app_with_permissions
    token = get_access_token(app, client_id, client_key)

    jobs = [
        {"job_queue": "myqueue2"},
        {"job_queue": "myqueue2", "job_priority": 200},
        {"job_queue": "myqueue2", "job_priority": 100},
    ]

    job_ids = []
    for job in jobs:
        job_response = app.post(
            "/v1/job", json=job, headers={"Authorization": token}
        )
        job_id = job_response.json.get("job_id")
        job_ids.append(job_id)

    job_positions = []
    for job_id in job_ids:
        job_positions.append(app.get(f"/v1/job/{job_id}/position").text)

    assert job_positions[0] == "2"
    assert job_positions[1] == "0"
    assert job_positions[2] == "1"


def test_restricted_queue_allowed(mongo_app_with_permissions):
    """
    Tests that jobs that submit to a restricted queue are accepted
    when the token allows that queue.
    """
    app, _, client_id, client_key, _ = mongo_app_with_permissions
    token = get_access_token(app, client_id, client_key)

    # rqueue1 is a restricted queue that is allowed for this client
    job = {"job_queue": "rqueue1"}
    job_response = app.post(
        "/v1/job", json=job, headers={"Authorization": token}
    )

    assert 200 == job_response.status_code


def test_restricted_queue_reject(mongo_app_with_permissions):
    """
    Tests that jobs that submit to a restricted queue are rejected
    when the client is not allowed.
    """
    app, _, client_id, client_key, _ = mongo_app_with_permissions
    token = get_access_token(app, client_id, client_key)

    # rqueue3 is a restricted queue that is not allowed for this client
    job = {"job_queue": "rqueue3"}
    job_response = app.post(
        "/v1/job", json=job, headers={"Authorization": token}
    )

    assert 403 == job_response.status_code


def test_restricted_queue_reject_no_token(mongo_app_with_permissions):
    """
    Tests that jobs that submit to a restricted queue are rejected
    when no token is included.
    """
    app, _, _, _, _ = mongo_app_with_permissions
    job = {"job_queue": "rqueue1"}
    job_response = app.post("/v1/job", json=job)
    assert job_response.status_code == HTTPStatus.UNAUTHORIZED
    message = job_response.get_json()["message"]
    assert "Authentication required to push to restricted queue" in message


def test_extended_reservation_allowed(mongo_app_with_permissions):
    """
    Tests that jobs that include extended reservation are accepted when
    the token gives them permission.
    """
    app, _, client_id, client_key, _ = mongo_app_with_permissions
    token = get_access_token(app, client_id, client_key)

    job = {"job_queue": "myqueue", "reserve_data": {"timeout": 30000}}
    job_response = app.post(
        "/v1/job", json=job, headers={"Authorization": token}
    )

    assert 200 == job_response.status_code


def test_extended_reservation_rejected(mongo_app_with_permissions):
    """
    Tests that jobs that include extended reservation are rejected when
    the token does not give them permission.
    """
    app, _, client_id, client_key, _ = mongo_app_with_permissions
    token = get_access_token(app, client_id, client_key)

    job = {"job_queue": "myqueue2", "reserve_data": {"timeout": 21601}}
    job_response = app.post(
        "/v1/job", json=job, headers={"Authorization": token}
    )

    assert 403 == job_response.status_code


def test_extended_reservation_reject_no_token(mongo_app_with_permissions):
    """
    Tests that jobs that included extended reservation are rejected
    when no token is included.
    """
    app, _, _, _, _ = mongo_app_with_permissions
    job = {"job_queue": "myqueue", "reserve_data": {"timeout": 21601}}
    job_response = app.post("/v1/job", json=job)
    assert job_response.status_code == HTTPStatus.UNAUTHORIZED
    message = job_response.get_json()["message"]
    assert "Authentication required for setting timeout" in message


def test_normal_reservation_no_token(mongo_app):
    """
    Tests that jobs that include reservation times less than the maximum
    are accepted when no token is included.
    """
    app, _ = mongo_app
    job = {"job_queue": "myqueue", "reserve_data": {"timeout": 21600}}
    job_response = app.post("/v1/job", json=job)
    assert 200 == job_response.status_code


def test_star_extended_reservation(mongo_app_with_permissions):
    """
    Tests submission to generic queue with extended reservation
    when client has star permissions.
    """
    app, mongo, client_id, client_key, _ = mongo_app_with_permissions
    mongo.client_permissions.find_one_and_update(
        {"client_id": client_id},
        {"$set": {"max_reservation_time": {"*": 30000}}},
    )
    token = get_access_token(app, client_id, client_key)

    job = {"job_queue": "myrandomqueue", "reserve_data": {"timeout": 30000}}
    job_response = app.post(
        "/v1/job", json=job, headers={"Authorization": token}
    )

    assert 200 == job_response.status_code


def test_get_all_restricted_queues(mongo_app_with_permissions):
    """Test retrieving all restricted queues for agents."""
    app, mongo, client_id, client_key, _ = mongo_app_with_permissions
    mongo.restricted_queues.delete_many({})
    token = get_access_token(app, client_id, client_key)

    mongo.agents.insert_many(
        [
            {
                "name": "agent1",
                "identifier": "202506-00001",
                "queues": ["q1", "q2"],
            },
            {"name": "agent2", "identifier": "202506-00002", "queues": ["q3"]},
        ]
    )
    mongo.restricted_queues.insert_many(
        [
            {"queue_name": "q1"},
            {"queue_name": "q3"},
        ]
    )
    mongo.client_permissions.insert_many(
        [
            {"client_id": "clientA", "allowed_queues": ["q1"]},
            {"client_id": "clientB", "allowed_queues": ["q3"]},
        ]
    )

    output = app.get("/v1/restricted-queues", headers={"Authorization": token})
    assert output.status_code == HTTPStatus.OK

    result = output.json
    expected = [
        {"queue": "q1", "owners": ["clientA"]},
        {"queue": "q3", "owners": ["clientB"]},
    ]
    assert result[0] in expected
    assert result[1] in expected


def test_get_restricted_queue(mongo_app_with_permissions):
    """Test retrieving info for a specific restricted queue."""
    app, mongo, client_id, client_key, _ = mongo_app_with_permissions
    mongo.restricted_queues.delete_many({})
    token = get_access_token(app, client_id, client_key)

    mongo.agents.insert_one(
        {
            "name": "agent1",
            "identifier": "202506-00001",
            "queues": ["q1", "q2"],
        },
    )
    mongo.restricted_queues.insert_one(
        {"queue_name": "202506-00001"},
    )
    mongo.client_permissions.insert_one(
        {"client_id": "clientA", "allowed_queues": ["202506-00001"]},
    )

    output = app.get(
        "/v1/restricted-queues/202506-00001", headers={"Authorization": token}
    )
    assert output.status_code == HTTPStatus.OK

    result = output.json
    expected = {"queue": "202506-00001", "owners": ["clientA"]}
    assert result == expected


def test_add_restricted_queue(mongo_app_with_permissions):
    """Test adding a restricted queue for an agent."""
    app, mongo, client_id, client_key, _ = mongo_app_with_permissions
    mongo.restricted_queues.delete_many({})
    token = get_access_token(app, client_id, client_key)

    client_entry = {
        "client_id": "clientA",
        "max_priority": {},
        "max_reservation_time": {},
        "role": ServerRoles.CONTRIBUTOR,
    }
    # Insert client
    mongo.client_permissions.insert_one(client_entry)

    mongo.agents.insert_one(
        {
            "name": "agent1",
            "identifier": "202506-00001",
            "queues": ["q1", "q2"],
        },
    )

    data = {
        "client_id": "clientA",
    }
    output = app.post(
        "/v1/restricted-queues/q2", json=data, headers={"Authorization": token}
    )
    assert output.status_code == HTTPStatus.OK

    permission = mongo.client_permissions.find_one({"client_id": "clientA"})
    assert "q2" in permission.get("allowed_queues", [])
    restricted_queue = mongo.restricted_queues.find_one({"queue_name": "q2"})
    assert restricted_queue is not None


def test_add_restricted_queue_client_not_exists(mongo_app_with_permissions):
    """Test add a restricted queue for an agent fails if client don't exist."""
    app, mongo, client_id, client_key, _ = mongo_app_with_permissions
    mongo.restricted_queues.delete_many({})
    token = get_access_token(app, client_id, client_key)

    mongo.agents.insert_one(
        {
            "name": "agent1",
            "identifier": "202506-00001",
            "queues": ["q1", "q2"],
        },
    )

    data = {
        "client_id": "clientA",
    }
    output = app.post(
        "/v1/restricted-queues/q2", json=data, headers={"Authorization": token}
    )
    assert output.status_code == HTTPStatus.NOT_FOUND
    assert "Specified client_id does not exist" in output.json["message"]

    # Client Permissions collection should be empty
    permission = mongo.client_permissions.find_one({"client_id": "clientA"})
    assert permission is None
    # Restricted queue should also be empty
    restricted_queue = mongo.restricted_queues.find_one({"queue_name": "q2"})
    assert restricted_queue is None


def test_delete_restricted_queue(mongo_app_with_permissions):
    """Test deleting a restricted queue for an agent."""
    app, mongo, client_id, client_key, _ = mongo_app_with_permissions
    mongo.restricted_queues.delete_many({})
    token = get_access_token(app, client_id, client_key)

    mongo.agents.insert_one(
        {
            "name": "agent1",
            "identifier": "202506-00001",
            "queues": ["q1"],
        },
    )
    mongo.restricted_queues.insert_one({"queue_name": "q1"})
    mongo.client_permissions.insert_one(
        {"client_id": "clientA", "allowed_queues": ["q1"]}
    )

    data = {"client_id": "clientA"}
    output = app.delete(
        "/v1/restricted-queues/q1", json=data, headers={"Authorization": token}
    )
    assert output.status_code == HTTPStatus.OK

    permission = mongo.client_permissions.find_one({"client_id": "clientA"})
    assert "q1" not in permission.get("allowed_queues", [])
    restricted_queue = mongo.restricted_queues.find_one({"queue_name": "q1"})
    assert restricted_queue is None


def test_get_all_client_permissions(mongo_app_with_permissions):
    """Test get all client_id and its permissions."""
    app, mongo, client_id, client_key, _ = mongo_app_with_permissions
    token = get_access_token(app, client_id, client_key)

    client_entry = {
        "client_id": "test_client",
        "max_priority": {},
        "allowed_queues": ["q1"],
        "max_reservation_time": {},
        "role": ServerRoles.CONTRIBUTOR,
    }
    # Insert client
    mongo.client_permissions.insert_one(client_entry)

    output = app.get(
        "/v1/client-permissions",
        headers={"Authorization": token},
    )

    assert output.status_code == HTTPStatus.OK
    assert "client_secret_hash" not in output.json
    # There are two clients, the admin and the recently created
    assert len(output.json) == 2

    # Cleanup test client
    mongo.client_permissions.delete_one({"client_id": "test_client"})


def test_get_single_client_permissions(mongo_app_with_permissions):
    """Test get single client_id and its permissions."""
    app, mongo, client_id, client_key, _ = mongo_app_with_permissions
    token = get_access_token(app, client_id, client_key)

    client_entry = {
        "client_id": "test_client",
        "max_priority": {},
        "allowed_queues": ["q1"],
        "max_reservation_time": {},
        "role": ServerRoles.CONTRIBUTOR,
    }
    # Insert client
    mongo.client_permissions.insert_one(client_entry)

    output = app.get(
        "/v1/client-permissions/my_client_id",
        headers={"Authorization": token},
    )

    assert output.status_code == HTTPStatus.OK
    for key, expected_value in client_entry.items():
        assert client_entry[key] == expected_value
    assert "client_secret_hash" not in output.json

    # Cleanup test client
    mongo.client_permissions.delete_one({"client_id": "test_client"})


def test_add_client_permissions(mongo_app_with_permissions):
    """Test adding a client_id and its permissions."""
    app, mongo, client_id, client_key, _ = mongo_app_with_permissions
    token = get_access_token(app, client_id, client_key)

    # Define client_id and permissions
    client_permissions = {
        "client_id": "test_client",
        "client_secret": "my-secret-password",
        "max_priority": {"*": 10},
        "max_reservation_time": {"*": 40000},
        "role": ServerRoles.CONTRIBUTOR,
    }

    output = app.post(
        "/v1/client-permissions",
        json=client_permissions,
        headers={"Authorization": token},
    )

    # Retrieve data from Database
    client_entry = mongo.client_permissions.find_one(
        {"client_id": "test_client"}
    )

    assert output.status_code == HTTPStatus.OK
    assert client_entry is not None

    # Check all fields match
    clear_password = client_permissions.pop("client_secret")
    for key, expected_value in client_permissions.items():
        assert client_entry[key] == expected_value

    # Validate clear secret is not in Database
    assert "client_secret" not in client_entry
    assert "client_secret_hash" in client_entry
    assert client_entry["client_secret_hash"] != clear_password

    # Cleanup test client
    mongo.client_permissions.delete_one({"client_id": "test_client"})


def test_edit_client_permissions(mongo_app_with_permissions):
    """Test editing a client_id and its permissions."""
    app, mongo, client_id, client_key, _ = mongo_app_with_permissions
    token = get_access_token(app, client_id, client_key)

    # Insert initial client directly in mongo
    initial_client = {
        "client_id": "test_client",
        "client_secret_hash": "hashed_password",
        "max_priority": {"q1": 10},
        "max_reservation_time": {},
        "role": ServerRoles.CONTRIBUTOR,
    }
    mongo.client_permissions.insert_one(initial_client)

    # Edit the client with updated permissions
    updated_permissions = {
        "max_priority": {},
        "max_reservation_time": {"*": 50000},
        "role": ServerRoles.MANAGER,
    }

    output = app.put(
        "/v1/client-permissions/test_client",
        json=updated_permissions,
        headers={"Authorization": token},
    )
    assert output.status_code == HTTPStatus.OK

    # Verify the updated data
    client_entry = mongo.client_permissions.find_one(
        {"client_id": "test_client"}
    )

    assert client_entry is not None
    assert client_entry["max_priority"] == {}
    assert client_entry["max_reservation_time"] == {"*": 50000}
    assert client_entry["role"] == ServerRoles.MANAGER

    # Ensure client_secret_hash is unchanged
    assert client_entry["client_secret_hash"] == "hashed_password"  # noqa S105

    # Cleanup test client
    mongo.client_permissions.delete_one({"client_id": "test_client"})


def test_delete_client_permissions(mongo_app_with_permissions):
    """Test deleting a client_id and its permissions."""
    app, mongo, client_id, client_key, _ = mongo_app_with_permissions
    token = get_access_token(app, client_id, client_key)

    # Insert client
    mongo.client_permissions.insert_one(
        {
            "client_id": "test_client",
            "max_priority": {},
            "allowed_queues": ["q1"],
            "max_reservation_time": {},
            "role": ServerRoles.CONTRIBUTOR,
        }
    )

    output = app.delete(
        "/v1/client-permissions/test_client", headers={"Authorization": token}
    )
    assert output.status_code == HTTPStatus.OK

    client_id_list = list(mongo.client_permissions.find({}))
    client_ids = [client["client_id"] for client in client_id_list]
    assert "clientA" not in client_ids


def test_delete_testflinger_admin(mongo_app_with_permissions):
    """Test deleting testflinger-admin is unsuccessful."""
    app, _, client_id, client_key, _ = mongo_app_with_permissions
    token = get_access_token(app, client_id, client_key)

    # No need to mock this client_id creation, request should be rejected
    output = app.delete(
        "/v1/client-permissions/testflinger-admin",
        headers={"Authorization": token},
    )
    assert output.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_create_client_permissions_invalid_role(mongo_app_with_permissions):
    """Test creating client with invalid role fails with schema validation."""
    app, _, client_id, client_key, _ = mongo_app_with_permissions
    token = get_access_token(app, client_id, client_key)

    # Send invalid role
    client_permissions = {
        "client_id": "test_client",
        "client_secret": "my-secret-password",
        "max_priority": {"*": 10},
        "max_reservation_time": {"*": 40000},
        "role": "invalid_role",
    }

    output = app.post(
        "/v1/client-permissions",
        json=client_permissions,
        headers={"Authorization": token},
    )

    assert output.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    error_response = output.json
    assert "role" in error_response["detail"]["json"]
    assert "Must be one of" in str(error_response["detail"]["json"]["role"])


def test_create_client_permissions_missing_required_fields(
    mongo_app_with_permissions,
):
    """Test creating client fails with schema validation."""
    app, mongo, client_id, client_key, _ = mongo_app_with_permissions
    token = get_access_token(app, client_id, client_key)

    # Missing required fields (max_priority, max_reservation_time)
    client_permissions = {
        "client_id": "test_client",
        "client_secret": "my-secret-password",
    }

    output = app.post(
        "/v1/client-permissions",
        json=client_permissions,
        headers={"Authorization": token},
    )

    assert output.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    error_response = output.json

    # Should have errors for missing fields
    json_errors = error_response["detail"]["json"]
    assert "max_priority" in json_errors
    assert "max_reservation_time" in json_errors


def test_create_client_permissions_duplicate_client(
    mongo_app_with_permissions,
):
    """Test creating duplicate client fails with conflict error."""
    app, mongo, client_id, client_key, _ = mongo_app_with_permissions
    token = get_access_token(app, client_id, client_key)

    client_permissions = {
        "client_id": "test_client",
        "client_secret": "my-secret-password",
        "max_priority": {"*": 10},
        "max_reservation_time": {"*": 40000},
        "role": ServerRoles.CONTRIBUTOR,
    }

    # Create client
    output1 = app.post(
        "/v1/client-permissions",
        json=client_permissions,
        headers={"Authorization": token},
    )
    assert output1.status_code == HTTPStatus.OK

    # Attempt to create same client
    output2 = app.post(
        "/v1/client-permissions",
        json=client_permissions,
        headers={"Authorization": token},
    )
    assert output2.status_code == HTTPStatus.CONFLICT
    error_response = output2.json
    assert "Client already exists" in error_response["message"]

    # Cleanup
    mongo.client_permissions.delete_one({"client_id": "test_client"})


def test_role_hierachy_edit_permissions(mongo_app_with_permissions):
    """Test that a lower level role can't edit permissions."""
    app, mongo, client_id, client_key, _ = mongo_app_with_permissions
    token = get_access_token(app, client_id, client_key)

    manager_permissions = {
        "client_id": "test_manager",
        "client_secret": "my-secret-password",
        "max_priority": {},
        "max_reservation_time": {},
        "role": ServerRoles.MANAGER,
    }

    # First create manager client_id
    output1 = app.post(
        "/v1/client-permissions",
        json=manager_permissions,
        headers={"Authorization": token},
    )
    assert output1.status_code == HTTPStatus.OK

    # Get manager token
    manager_auth_output = app.post(
        "/v1/oauth2/token",
        headers=create_auth_header("test_manager", "my-secret-password"),
    )
    manager_token = manager_auth_output.get_json()["access_token"]

    # Attempt to demote admin account from fixture
    updated_permissions = {
        "role": ServerRoles.CONTRIBUTOR,
        "max_priority": {},
        "max_reservation_time": {},
    }
    output2 = app.put(
        f"/v1/client-permissions/{client_id}",
        json=updated_permissions,
        headers={"Authorization": manager_token},
    )
    assert output2.status_code == HTTPStatus.FORBIDDEN
    error_response = output2.json
    assert "Insufficient permissions to modify" in error_response["message"]

    # Cleanup
    mongo.client_permissions.delete_one({"client_id": "test_manager"})


def test_role_hierachy_create_permissions(mongo_app_with_permissions):
    """Test that a lower level role can't create higher level accounts."""
    app, mongo, client_id, client_key, _ = mongo_app_with_permissions
    token = get_access_token(app, client_id, client_key)

    manager_permissions = {
        "client_id": "test_manager",
        "client_secret": "my-secret-password",
        "max_priority": {},
        "max_reservation_time": {},
        "role": ServerRoles.MANAGER,
    }

    # First create manager client_id
    output1 = app.post(
        "/v1/client-permissions",
        json=manager_permissions,
        headers={"Authorization": token},
    )
    assert output1.status_code == HTTPStatus.OK

    # Get manager token
    manager_auth_output = app.post(
        "/v1/oauth2/token",
        headers=create_auth_header("test_manager", "my-secret-password"),
    )
    manager_token = manager_auth_output.get_json()["access_token"]

    # Attempt to create new admin account
    admin_permissions = {
        "client_id": "new_admin",
        "client_secret": "my-admin-secret",
        "role": ServerRoles.ADMIN,
        "max_priority": {"*": 100},
        "max_reservation_time": {"*": 20000},
    }
    output2 = app.post(
        "/v1/client-permissions",
        json=admin_permissions,
        headers={"Authorization": manager_token},
    )
    assert output2.status_code == HTTPStatus.FORBIDDEN
    error_response = output2.json
    assert "Insufficient permissions to create" in error_response["message"]

    # Cleanup
    mongo.client_permissions.delete_one({"client_id": "test_manager"})


def test_refresh_access_token(mongo_app_with_permissions):
    """Test refreshing an access token with a valid refresh token."""
    app, _, client_id, client_key, max_priority = mongo_app_with_permissions

    initial = app.post(
        "/v1/oauth2/token",
        headers=create_auth_header(client_id, client_key),
    )
    initial_json = initial.get_json()
    refresh_token = initial_json["refresh_token"]

    refreshed = app.post(
        "/v1/oauth2/refresh",
        json={"token": refresh_token},
    )
    assert refreshed.status_code == HTTPStatus.OK
    refreshed_json = refreshed.get_json()

    decoded = jwt.decode(
        refreshed_json["access_token"],
        os.environ.get("JWT_SIGNING_KEY"),
        algorithms="HS256",
        options={"require": ["exp", "iat", "sub", "permissions"]},
    )
    assert decoded["permissions"]["max_priority"] == max_priority


def test_refresh_with_invalid_token(mongo_app_with_permissions):
    """Test refresh with a invalid token string."""
    app, _, _, _, _ = mongo_app_with_permissions

    resp = app.post(
        "/v1/oauth2/refresh",
        json={"token": "not-a-real-token"},
    )
    assert resp.status_code == HTTPStatus.BAD_REQUEST


def test_refresh_with_expired_token(mongo_app_with_permissions):
    """Test refresh fails if the refresh token is expired."""
    app, mongo, client_id, client_key, _ = mongo_app_with_permissions

    issued = app.post(
        "/v1/oauth2/token",
        headers=create_auth_header(client_id, client_key),
    )
    refresh_token = issued.get_json()["refresh_token"]

    mongo.refresh_tokens.update_one(
        {"refresh_token": refresh_token},
        {
            "$set": {
                "expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)
            }
        },
    )

    resp = app.post(
        "/v1/oauth2/refresh",
        json={"token": refresh_token},
    )
    assert resp.status_code == HTTPStatus.BAD_REQUEST


def test_refresh_with_missing_token_field(mongo_app_with_permissions):
    """Test refresh fails if token field is missing."""
    app, _, _, _, _ = mongo_app_with_permissions

    resp = app.post("/v1/oauth2/refresh", json={})
    assert resp.status_code == HTTPStatus.BAD_REQUEST


def test_revoke_refresh_token(mongo_app_with_permissions):
    """Test that admin can revoke refresh token."""
    app, mongo, client_id, client_key, _ = mongo_app_with_permissions
    admin_token = get_access_token(app, client_id, client_key)

    contributor_permissions = {
        "client_id": "test_user",
        "client_secret": "user-secret",
        "max_priority": {},
        "max_reservation_time": {},
        "role": ServerRoles.CONTRIBUTOR,
    }
    output = app.post(
        "/v1/client-permissions",
        json=contributor_permissions,
        headers={"Authorization": admin_token},
    )
    assert output.status_code == HTTPStatus.OK

    contributor_auth_output = app.post(
        "/v1/oauth2/token",
        headers=create_auth_header("test_user", "user-secret"),
    )
    assert contributor_auth_output.status_code == HTTPStatus.OK
    refresh_token = contributor_auth_output.get_json()["refresh_token"]

    revoked = app.post(
        "/v1/oauth2/revoke",
        json={"token": refresh_token},
        headers={"Authorization": admin_token},
    )
    assert revoked.status_code == HTTPStatus.OK
    assert revoked.get_json()["status"] == "OK"

    refreshed = app.post(
        "/v1/oauth2/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refreshed.status_code == HTTPStatus.BAD_REQUEST

    mongo.client_permissions.delete_one({"client_id": "test_user"})
    mongo.refresh_tokens.delete_one({"client_id": "test_user"})


def test_non_admin_cannot_revoke_refresh_token(mongo_app_with_permissions):
    """Test that non-admin cannot revoke any refresh token."""
    app, mongo, client_id, client_key, _ = mongo_app_with_permissions
    admin_token = get_access_token(app, client_id, client_key)

    user_perm = {
        "client_id": "test_user",
        "client_secret": "user-secret",
        "max_priority": {},
        "max_reservation_time": {},
        "role": ServerRoles.CONTRIBUTOR,
    }
    app.post(
        "/v1/client-permissions",
        json=user_perm,
        headers={"Authorization": admin_token},
    )

    contributor_auth_output = app.post(
        "/v1/oauth2/token",
        headers=create_auth_header("test_user", "user-secret"),
    )
    user_json = contributor_auth_output.get_json()
    user_access_token = user_json["access_token"]
    user_refresh_token = user_json["refresh_token"]

    attempt = app.post(
        "/v1/oauth2/revoke",
        json={"token": user_refresh_token},
        headers={"Authorization": user_access_token},
    )
    assert attempt.status_code == HTTPStatus.FORBIDDEN

    mongo.client_permissions.delete_one({"client_id": "test_user"})
    mongo.refresh_tokens.delete_many({"client_id": "test_user"})


def test_revoke_with_missing_token_field(mongo_app_with_permissions):
    """Test revoke fails if token field is missing."""
    app, mongo, client_id, client_key, _ = mongo_app_with_permissions
    token = get_access_token(app, client_id, client_key)

    resp = app.post(
        "/v1/oauth2/revoke", json={}, headers={"Authorization": token}
    )
    assert resp.status_code == HTTPStatus.BAD_REQUEST


def test_revoke_already_revoked_token(mongo_app_with_permissions):
    """Test revoking an already revoked token."""
    app, mongo, client_id, client_key, _ = mongo_app_with_permissions
    token = get_access_token(app, client_id, client_key)

    user_perm = {
        "client_id": "test_user",
        "client_secret": "user-secret",
        "max_priority": {},
        "max_reservation_time": {},
        "role": ServerRoles.CONTRIBUTOR,
    }
    app.post(
        "/v1/client-permissions",
        json=user_perm,
        headers={"Authorization": token},
    )

    user_auth = app.post(
        "/v1/oauth2/token",
        headers=create_auth_header("test_user", "user-secret"),
    )
    refresh_token = user_auth.get_json()["refresh_token"]

    resp1 = app.post(
        "/v1/oauth2/revoke",
        json={"token": refresh_token},
        headers={"Authorization": token},
    )
    assert resp1.status_code == HTTPStatus.OK

    resp2 = app.post(
        "/v1/oauth2/revoke",
        json={"token": refresh_token},
        headers={"Authorization": token},
    )
    assert resp2.status_code in (HTTPStatus.OK, HTTPStatus.BAD_REQUEST)
