# Copyright (C) 2025 Canonical
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

"""Tests for the `v1/secrets` endpoints."""

import base64
import os
from datetime import datetime, timezone
from http import HTTPStatus

import bcrypt
import mongomock
import pytest

from testflinger import application, database
from testflinger.secrets.exceptions import AccessError, StoreError
from testflinger.secrets.vault import VaultStore


@pytest.fixture
def app_with_store(mocker):
    """Create a pytest fixture for an app with a database and store."""
    os.environ["JWT_SIGNING_KEY"] = "my_secret_key"
    mock_mongo = mongomock.MongoClient()

    # mock database
    database.mongo = mock_mongo
    mongo = mock_mongo.db

    # populate database with client data
    for client_id, client_key in (
        ("client_1", "client_key"),
        ("client_2", "client_key"),
    ):
        client_salt = bcrypt.gensalt()
        client_key_hash = bcrypt.hashpw(
            client_key.encode("utf-8"), client_salt
        ).decode("utf-8")
        mongo.client_permissions.insert_one(
            {
                "client_id": client_id,
                "client_secret_hash": client_key_hash,
            }
        )

    # mock store
    mock_vault_store = mocker.Mock(spec=VaultStore)

    # create app
    flask_app = application.create_flask_app(
        type("", (), {"TESTING": True})(),
        secrets_store=mock_vault_store,
    )
    yield flask_app.test_client()


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


@pytest.mark.parametrize(
    "client_id,path,value",
    (
        ("client_1", "shallow", "shallow_value"),
        ("client_1", "path/with/components", "deep_value"),
        ("client_2", "another/path", "another_value"),
    ),
)
def test_secrets_put_success(app_with_store, client_id, path, value):
    """Test successfully writing a secret to the store through the API."""
    # GIVEN: an app with a secrets store
    mock_secrets_store = app_with_store.application.secrets_store
    mock_secrets_store.write.return_value = None

    # WHEN: an authorised request is sent to the PUT secrets endpoint
    token = get_access_token(app_with_store, client_id, "client_key")
    response = app_with_store.put(
        f"/v1/secrets/{client_id}/{path}",
        json={"value": value},
        headers={"Authorization": token},
    )

    # THEN: the request is successful
    assert response.status_code == HTTPStatus.OK
    mock_secrets_store.write.assert_called_once_with(client_id, path, value)


def test_secrets_put_different_client_id(app_with_store):
    """Test writing a secret to an unauthorized namespace."""
    # GIVEN: an app with a secrets store
    client_id = "client_1"
    unauthorized_client_id = "client_2"
    path = "path/to/secret"
    mock_secrets_store = app_with_store.application.secrets_store

    # WHEN: an authorised request for a different client id is sent to
    #   the PUT secrets endpoint
    token = get_access_token(app_with_store, client_id, "client_key")
    response = app_with_store.put(
        f"/v1/secrets/{unauthorized_client_id}/{path}",
        json={"value": "value"},
        headers={"Authorization": token},
    )

    # THEN: the request is rejected and no secret has been written
    assert response.status_code == HTTPStatus.FORBIDDEN
    mock_secrets_store.write.assert_not_called()


def test_secrets_put_no_value(app_with_store):
    """Test writing a secret without providing a value."""
    # GIVEN: an app with a secrets store
    client_id = "client_1"
    path = "path/to/secret"
    mock_secrets_store = app_with_store.application.secrets_store

    # WHEN: an authorised request without a value is sent to the
    #   PUT secrets endpoint
    token = get_access_token(app_with_store, client_id, "client_key")
    response = app_with_store.put(
        f"/v1/secrets/{client_id}/{path}",
        headers={"Authorization": token},
    )

    # THEN: the request is rejected and no secret has been written
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    mock_secrets_store.write.assert_not_called()


def test_secrets_put_no_authentication(app_with_store):
    """Test writing a secret when unauthorized."""
    # GIVEN: an app with a secrets store
    client_id = "client_1"
    path = "path/to/secret"
    mock_secrets_store = app_with_store.application.secrets_store

    # WHEN: an unauthorised request is sent to the PUT secrets endpoint
    response = app_with_store.put(
        f"/v1/secrets/{client_id}/{path}",
        json={"value": "value"},
    )

    # THEN: the request is rejected and no secret has been written
    assert response.status_code == HTTPStatus.FORBIDDEN
    mock_secrets_store.write.assert_not_called()


def test_secrets_put_access_error(app_with_store):
    """Test writing a secret with an access error from the store."""
    # GIVEN: an app with a secrets store where write raises an AccessErrpr
    client_id = "client_1"
    path = "path/to/error/access"
    mock_secrets_store = app_with_store.application.secrets_store
    mock_secrets_store.write.side_effect = AccessError()

    # WHEN: an authorised request is sent to the PUT secrets endpoint
    token = get_access_token(app_with_store, client_id, "client_key")
    response = app_with_store.put(
        f"/v1/secrets/{client_id}/{path}",
        json={"value": "value"},
        headers={"Authorization": token},
    )

    # THEN: the request is rejected
    assert response.status_code == HTTPStatus.BAD_REQUEST
    mock_secrets_store.write.assert_called_once_with(client_id, path, "value")


def test_secrets_put_store_error(app_with_store):
    """Test writing a secret with a store error."""
    # GIVEN: an app with a secrets store where write raises a StoreError
    client_id = "client_1"
    path = "path/to/error/store"
    mock_secrets_store = app_with_store.application.secrets_store
    mock_secrets_store.write.side_effect = StoreError()

    # WHEN: an authorised request is sent to the PUT secrets endpoint
    token = get_access_token(app_with_store, client_id, "client_key")
    response = app_with_store.put(
        f"/v1/secrets/{client_id}/{path}",
        json={"value": "value"},
        headers={"Authorization": token},
    )

    # THEN: the request is rejected
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    mock_secrets_store.write.assert_called_once_with(client_id, path, "value")


def test_secrets_put_no_store(testapp):
    """Test writing a secret without having set up a secrets store."""
    # GIVEN: an app without a secrets store
    client_id = "client_1"
    path = "path/to/secret"
    app_client = testapp.test_client()

    # WHEN: a request is sent to the PUT secrets endpoint
    response = app_client.put(
        f"/v1/secrets/{client_id}/{path}",
        json={"value": "value"},
    )

    # THEN: the request is rejected
    assert response.status_code == HTTPStatus.BAD_REQUEST


@pytest.mark.parametrize(
    "client_id,path",
    (
        ("client_1", "shallow"),
        ("client_1", "path/with/components"),
        ("client_2", "another/path"),
    ),
)
def test_secrets_delete_success(app_with_store, client_id, path):
    """Test successfully deleting a secret from the store through the API."""
    # GIVEN: an app with a secrets store
    mock_secrets_store = app_with_store.application.secrets_store
    mock_secrets_store.delete.return_value = None

    # WHEN: an authorised request is sent to the DELETE secrets endpoint
    token = get_access_token(app_with_store, client_id, "client_key")
    response = app_with_store.delete(
        f"/v1/secrets/{client_id}/{path}",
        headers={"Authorization": token},
    )

    # THEN: the request is successful
    assert response.status_code == HTTPStatus.OK
    mock_secrets_store.delete.assert_called_once_with(client_id, path)


def test_secrets_delete_different_client_id(app_with_store):
    """Test deleting a secret from an unauthorized namespace."""
    # GIVEN: an app with a secrets store
    client_id = "client_1"
    unauthorized_client_id = "client_2"
    path = "path/to/secret"
    mock_secrets_store = app_with_store.application.secrets_store

    # WHEN: an authorised request for a different client id is sent to
    #   the DELETE secrets endpoint
    token = get_access_token(app_with_store, client_id, "client_key")
    response = app_with_store.delete(
        f"/v1/secrets/{unauthorized_client_id}/{path}",
        headers={"Authorization": token},
    )

    # THEN: the request is rejected and no secret has been deleted
    assert response.status_code == HTTPStatus.FORBIDDEN
    mock_secrets_store.delete.assert_not_called()


def test_secrets_delete_no_authentication(app_with_store):
    """Test deleting a secret when unauthorized."""
    # GIVEN: an app with a secrets store
    client_id = "client_1"
    path = "path/to/secret"
    mock_secrets_store = app_with_store.application.secrets_store

    # WHEN: an unauthorised request is sent to the DELETE secrets endpoint
    response = app_with_store.delete(
        f"/v1/secrets/{client_id}/{path}",
    )

    # THEN: the request is rejected and no secret has been deleted
    assert response.status_code == HTTPStatus.FORBIDDEN
    mock_secrets_store.delete.assert_not_called()


def test_secrets_delete_access_error(app_with_store):
    """Test deleting a secret with an access error from the store."""
    # GIVEN: an app with a secrets store where delete raises an AccessError
    client_id = "client_1"
    path = "path/to/error/access"
    mock_secrets_store = app_with_store.application.secrets_store
    mock_secrets_store.delete.side_effect = AccessError()

    # WHEN: an authorised request is sent to the DELETE secrets endpoint
    token = get_access_token(app_with_store, client_id, "client_key")
    response = app_with_store.delete(
        f"/v1/secrets/{client_id}/{path}",
        headers={"Authorization": token},
    )

    # THEN: the request is rejected
    assert response.status_code == HTTPStatus.BAD_REQUEST
    mock_secrets_store.delete.assert_called_once_with(client_id, path)


def test_secrets_delete_store_error(app_with_store):
    """Test deleting a secret with a store error."""
    # GIVEN: an app with a secrets store where delete raises a StoreError
    client_id = "client_1"
    path = "path/to/error/store"
    mock_secrets_store = app_with_store.application.secrets_store
    mock_secrets_store.delete.side_effect = StoreError()

    # WHEN: an authorised request is sent to the DELETE secrets endpoint
    token = get_access_token(app_with_store, client_id, "client_key")
    response = app_with_store.delete(
        f"/v1/secrets/{client_id}/{path}",
        headers={"Authorization": token},
    )

    # THEN: the request is rejected
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    mock_secrets_store.delete.assert_called_once_with(client_id, path)


def test_secrets_delete_no_store(testapp):
    """Test deleting a secret without having set up a secrets store."""
    # GIVEN: an app without a secrets store
    client_id = "client_1"
    path = "path/to/secret"
    app_client = testapp.test_client()

    # WHEN: a request is sent to the DELETE secrets endpoint
    response = app_client.delete(
        f"/v1/secrets/{client_id}/{path}",
    )

    # THEN: the request is rejected
    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_job_submit_with_secrets(app_with_store):
    """Test that submitting a job with valid secrets works."""
    # GIVEN: an app with a secrets store that returns values for valid paths
    client_id = "client_1"
    mock_secrets_store = app_with_store.application.secrets_store
    mock_secrets_store.read.return_value = "secret_value"

    # WHEN: an authenticated job with secrets is submitted
    token = get_access_token(app_with_store, client_id, "client_key")
    job_data = {
        "job_queue": "test",
        "test_data": {
            "secrets": {
                "SECRET_KEY": "path/to/secret",
                "API_TOKEN": "tokens/api_key",
            }
        },
    }

    response = app_with_store.post(
        "/v1/job", json=job_data, headers={"Authorization": f"Bearer {token}"}
    )

    # THEN: the job is accepted and secrets are validated
    assert response.status_code == HTTPStatus.OK
    mock_secrets_store.read.assert_any_call(client_id, "path/to/secret")
    mock_secrets_store.read.assert_any_call(client_id, "tokens/api_key")

    # AND: the client_id is added to the job data in the database
    job_id = response.get_json()["job_id"]
    stored_job_data = database.mongo.db.jobs.find_one({"job_id": job_id})
    assert stored_job_data["job_data"]["client_id"] == client_id


def test_job_submit_with_inaccessible_secret(app_with_store):
    """Test that submitting a job with an inaccessible secret fails."""
    # GIVEN: an app with a secrets store where read raises an AccessError
    client_id = "client_1"
    mock_secrets_store = app_with_store.application.secrets_store
    mock_secrets_store.read.side_effect = AccessError("Secret not found")

    # WHEN: an authenticated job with invalid secrets is submitted
    token = get_access_token(app_with_store, client_id, "client_key")
    job_data = {
        "job_queue": "test",
        "test_data": {"secrets": {"INVALID_SECRET": "nonexistent/path"}},
    }

    response = app_with_store.post(
        "/v1/job", json=job_data, headers={"Authorization": f"Bearer {token}"}
    )

    # THEN: the job is rejected with appropriate error message
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert (
        "Inaccessible secret paths: nonexistent/path"
        in response.get_json()["message"]
    )


def test_job_submit_with_some_inaccessible_secrets(app_with_store):
    """Test that submitting a job with inaccessible secrets fails."""
    # GIVEN: an app with a secrets store where one path exists and one doesn't
    client_id = "client_1"
    mock_secrets_store = app_with_store.application.secrets_store

    def mock_read(client_id, path):
        if path == "valid/path":
            return "secret_value"
        else:
            raise AccessError("Secret not found")

    mock_secrets_store.read.side_effect = mock_read

    # WHEN: an authenticated job with an inaccessible secret is submitted
    token = get_access_token(app_with_store, client_id, "client_key")
    job_data = {
        "job_queue": "test",
        "test_data": {
            "secrets": {
                "VALID_SECRET": "valid/path",
                "INVALID_SECRET1": "other/path",
                "INVALID_SECRET2": "another/path",
            }
        },
    }

    response = app_with_store.post(
        "/v1/job", json=job_data, headers={"Authorization": f"Bearer {token}"}
    )

    # THEN: the job is rejected and only the invalid path is listed
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    message = response.get_json()["message"]
    assert "Inaccessible secret paths: another/path, other/path" == message
    assert "valid/path" not in message


def test_job_submit_with_secrets_no_store(testapp):
    """Test submitting a job with secrets without a secrets store."""
    # GIVEN: an app without a secrets store
    app_client = testapp.test_client()

    # WHEN: a job with secrets is submitted
    job_data = {
        "job_queue": "test",
        "test_data": {"secrets": {"SECRET_KEY": "path/to/secret"}},
    }

    response = app_client.post("/v1/job", json=job_data)

    # THEN: the job is rejected
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert "No secrets store" in response.get_json()["message"]


def test_job_submit_with_secrets_no_authentication(app_with_store):
    """Test that submitting a job with secrets fails when not authenticated."""
    # GIVEN: an app with a secrets store

    # WHEN: an unauthenticated job with secrets is submitted
    job_data = {
        "job_queue": "test",
        "test_data": {"secrets": {"SECRET_KEY": "path/to/secret"}},
    }

    response = app_with_store.post("/v1/job", json=job_data)

    # THEN: the job is rejected due to missing authentication
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert "Missing client ID" in response.get_json()["message"]


@pytest.mark.parametrize(
    "secrets",
    [
        # Invalid environment variable names
        ({"123_INVALID": "valid/path"},),
        ({"INVALID-NAME": "valid/path"},),
        ({"INVALID NAME": "valid/path"},),
        ({"INVALID.NAME": "valid/path"},),
        ({"": "valid/path"}),
        # Invalid secret paths
        ({"VALID_NAME": "invalid path"},),
        ({"VALID_NAME": "invalid@path"},),
        ({"VALID_NAME": "invalid\\path"},),
        ({"VALID_NAME": ""}),
    ],
)
def test_job_submit_with_invalid_secrets(app_with_store, secrets):
    """Test that submitting a job with invalid secrets is rejected."""
    # GIVEN: an app with a secrets store
    client_id = "client_1"

    # WHEN: an authenticated job with invalid secret format is submitted
    token = get_access_token(app_with_store, client_id, "client_key")
    job_data = {"job_queue": "test", "test_data": {"secrets": secrets}}

    response = app_with_store.post(
        "/v1/job", json=job_data, headers={"Authorization": f"Bearer {token}"}
    )

    # THEN: the job is rejected due to validation error
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert "Validation error" in response.get_json()["message"]


def test_job_get_with_secrets(app_with_store):
    """Test retrieving a job with secrets from the queue."""
    # GIVEN: an app with a secrets store and a job with secrets submitted
    client_id = "client_1"
    mock_secrets_store = app_with_store.application.secrets_store
    mock_secrets_store.read.side_effect = (
        lambda client_id, path: f"secret_value_for_{path}"
    )

    # Submit a job with secrets first
    token = get_access_token(app_with_store, client_id, "client_key")
    job_data = {
        "job_queue": "test",
        "test_data": {
            "secrets": {
                "SECRET_KEY": "path/to/secret",
                "API_TOKEN": "tokens/api_key",
            }
        },
    }

    submit_response = app_with_store.post(
        "/v1/job", json=job_data, headers={"Authorization": f"Bearer {token}"}
    )
    assert submit_response.status_code == HTTPStatus.OK

    # WHEN: a job is retrieved from the queue
    response = app_with_store.get("/v1/job?queue=test")

    # THEN: the job is returned with resolved secrets
    assert response.status_code == HTTPStatus.OK
    job = response.get_json()
    secrets = job["test_data"]["secrets"]
    for identifier, path in job_data["test_data"]["secrets"].items():
        assert secrets[identifier] == f"secret_value_for_{path}"

    # AND: the secrets store was called with the correct parameters
    mock_secrets_store.read.assert_any_call(client_id, "path/to/secret")
    mock_secrets_store.read.assert_any_call(client_id, "tokens/api_key")


def test_job_get_with_inaccessible_secrets(app_with_store):
    """Test retrieving a job when some secrets are inaccessible."""
    # GIVEN: an app with a secrets store and a job with secrets submitted
    client_id = "client_1"
    secret_value = "secret_value"  # noqa: S105
    mock_secrets_store = app_with_store.application.secrets_store

    # Submit a job with secrets first
    token = get_access_token(app_with_store, client_id, "client_key")
    job_data = {
        "job_queue": "test",
        "test_data": {
            "secrets": {
                "VALID_SECRET": "valid/path",
                "INVALID_SECRET": "invalid/path",
            }
        },
    }

    submit_response = app_with_store.post(
        "/v1/job", json=job_data, headers={"Authorization": f"Bearer {token}"}
    )
    assert submit_response.status_code == HTTPStatus.OK

    def mock_read_mixed(client_id, path):
        if path == "valid/path":
            return secret_value
        else:
            raise AccessError("Secret not found")

    mock_secrets_store.read.side_effect = mock_read_mixed

    # WHEN: a job is retrieved from the queue
    response = app_with_store.get("/v1/job?queue=test")

    # THEN: the job is returned with mixed secret values
    assert response.status_code == HTTPStatus.OK
    job = response.get_json()
    assert "secrets" in job["test_data"]
    assert job["test_data"]["secrets"]["VALID_SECRET"] == secret_value
    assert job["test_data"]["secrets"]["INVALID_SECRET"] == ""


def test_job_get_without_secrets(app_with_store):
    """Test retrieving a job that doesn't have secrets."""
    # GIVEN: an app with a secrets store and a job without secrets submitted
    client_id = "client_1"

    # Submit a job without secrets first
    token = get_access_token(app_with_store, client_id, "client_key")
    job_data = {"job_queue": "test"}

    submit_response = app_with_store.post(
        "/v1/job", json=job_data, headers={"Authorization": f"Bearer {token}"}
    )
    assert submit_response.status_code == HTTPStatus.OK

    # WHEN: a job is retrieved from the queue
    response = app_with_store.get("/v1/job?queue=test")

    # THEN: the job is returned without secrets field
    assert response.status_code == HTTPStatus.OK
    job = response.get_json()

    if "test_data" in job:
        assert "secrets" not in job["test_data"]


def test_job_get_with_secrets_no_store(testapp):
    """Test retrieving a job with secrets without a secrets store."""
    # GIVEN: an app without a secrets store
    app_client = testapp.test_client()

    # Manually insert a job with secrets into the database (simulating a job
    # submitted when store was available but now unavailable)
    job_id = "test-job-id-1234"
    job_data = {
        "job_queue": "test",
        "test_data": {"secrets": {"SECRET_KEY": "path/to/secret"}},
        "client_id": "client_1",
    }
    database.mongo.db.jobs.insert_one(
        {
            "job_id": job_id,
            "job_data": job_data,
            "created_at": datetime.now(timezone.utc),
            "result_data": {"job_state": "waiting"},
            "job_priority": 0,
        }
    )

    # WHEN: a job is retrieved from the queue
    response = app_client.get("/v1/job?queue=test")

    # THEN: the job is returned with empty secret values
    assert response.status_code == HTTPStatus.OK
    job = response.get_json()
    assert "secrets" in job["test_data"]
    assert job["test_data"]["secrets"]["SECRET_KEY"] == ""


def test_job_get_with_missing_client_id(app_with_store):
    """Test retrieving a job with secrets but missing client_id."""
    # GIVEN: an app with a secrets store
    mock_secrets_store = app_with_store.application.secrets_store

    # Manually insert a job with secrets but no client_id
    job_id = "test-job-id-1234"
    job_data = {
        "job_queue": "test",
        "test_data": {"secrets": {"SECRET_KEY": "path/to/secret"}},
    }
    database.mongo.db.jobs.insert_one(
        {
            "job_id": job_id,
            "job_data": job_data,
            "created_at": datetime.now(timezone.utc),
            "result_data": {"job_state": "waiting"},
            "job_priority": 0,
        }
    )

    # WHEN: a job is retrieved from the queue
    response = app_with_store.get("/v1/job?queue=test")

    # THEN: the job is returned with empty secret values
    assert response.status_code == HTTPStatus.OK
    job = response.get_json()
    assert "secrets" in job["test_data"]
    assert job["test_data"]["secrets"]["SECRET_KEY"] == ""

    # AND: the secrets store should not have been called
    mock_secrets_store.read.assert_not_called()
