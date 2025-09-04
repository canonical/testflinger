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
#

import base64
import os
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
    """Create authorization header for testing."""
    id_key_pair = f"{client_id}:{client_key}"
    base64_encoded_pair = base64.b64encode(id_key_pair.encode("utf-8")).decode(
        "utf-8"
    )
    return {"Authorization": f"Basic {base64_encoded_pair}"}


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
    auth_header = create_auth_header(client_id, "client_key")
    token_response = app_with_store.post(
        "/v1/oauth2/token", headers=auth_header
    )
    token = token_response.data.decode("utf-8")
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
    auth_header = create_auth_header(client_id, "client_key")
    token_response = app_with_store.post(
        "/v1/oauth2/token", headers=auth_header
    )
    token = token_response.data.decode("utf-8")
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

    # Configure the mock to raise AccessError for any read attempts
    mock_secrets_store.read.side_effect = AccessError()

    # WHEN: an authorised request without a value is sent to the
    #   PUT secrets endpoint
    auth_header = create_auth_header(client_id, "client_key")
    token_response = app_with_store.post(
        "/v1/oauth2/token", headers=auth_header
    )
    token = token_response.data.decode("utf-8")
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

    # Configure the mock to raise AccessError for any read attempts
    mock_secrets_store.read.side_effect = AccessError()

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
    # GIVEN: an app with a secrets store
    client_id = "client_1"
    path = "path/to/error/access"
    mock_secrets_store = app_with_store.application.secrets_store
    mock_secrets_store.write.side_effect = AccessError()

    # WHEN: an authorised request is sent to the PUT secrets endpoint
    auth_header = create_auth_header(client_id, "client_key")
    token_response = app_with_store.post(
        "/v1/oauth2/token", headers=auth_header
    )
    token = token_response.data.decode("utf-8")
    response = app_with_store.put(
        f"/v1/secrets/{client_id}/{path}",
        json={"value": "value"},
        headers={"Authorization": token},
    )

    # THEN: the request is rejected
    assert response.status_code == HTTPStatus.BAD_REQUEST
    mock_secrets_store.write.assert_called_once_with(client_id, path, "value")


def test_secrets_put_store_error(app_with_store):
    """Test writing a secret with an store error."""
    # GIVEN: an app with a secrets store
    client_id = "client_1"
    path = "path/to/error/store"
    mock_secrets_store = app_with_store.application.secrets_store
    mock_secrets_store.write.side_effect = StoreError()

    # WHEN: an authorised request is sent to the PUT secrets endpoint
    auth_header = create_auth_header(client_id, "client_key")
    token_response = app_with_store.post(
        "/v1/oauth2/token", headers=auth_header
    )
    token = token_response.data.decode("utf-8")
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
