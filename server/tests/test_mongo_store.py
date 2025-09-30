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

"""Tests for the MongoDB-based implementation of the secrets store."""

import base64
import os

import pytest
from bson.binary import Binary
from pymongo import MongoClient
from pymongo.encryption import ClientEncryption
from pymongo.errors import ConnectionFailure, EncryptionError, OperationFailure

from testflinger.secrets import setup_mongo_store
from testflinger.secrets.exceptions import (
    AccessError,
    StoreError,
)
from testflinger.secrets.mongo import MongoStore


class TestMongoStore:
    """Test cases for MongoStore class."""

    @pytest.fixture
    def mock_client(self, mocker):
        """Mock MongoClient."""
        return mocker.Mock(spec=MongoClient)

    @pytest.fixture
    def mock_client_encryption(self, mocker):
        """Mock ClientEncryption."""
        return mocker.Mock(spec=ClientEncryption)

    @pytest.fixture
    def mock_database(self, mocker):
        """Mock database object."""
        return mocker.Mock()

    @pytest.fixture
    def mongo_store(self, mock_client, mock_client_encryption, mock_database):
        """MongoStore instance with mocked dependencies."""
        mock_client.get_default_database.return_value = mock_database
        return MongoStore(mock_client, mock_client_encryption, "test-key")

    @pytest.fixture
    def mock_collection(self, mock_database, mocker):
        """Mock collection object."""
        collection = mocker.Mock()
        mock_database.secrets.__getitem__ = mocker.Mock(
            return_value=collection
        )
        return collection

    def test_read_success(
        self, mongo_store, mock_collection, mock_client_encryption
    ):
        """Test successful secret read."""
        encrypted_value = Binary(b"encrypted_data")
        mock_collection.find_one.return_value = {
            "key": "test-key",
            "value": encrypted_value,
        }
        mock_client_encryption.decrypt.return_value = b"test-secret-value"

        result = mongo_store.read("test-namespace", "test-key")

        assert result == "test-secret-value"
        mock_collection.find_one.assert_called_once_with({"key": "test-key"})
        mock_client_encryption.decrypt.assert_called_once_with(encrypted_value)

    def test_read_document_not_found(self, mongo_store, mock_collection):
        """Test read when document doesn't exist raises AccessError."""
        mock_collection.find_one.return_value = None

        with pytest.raises(
            AccessError,
            match="Unable to access 'test-key' under 'test-namespace'",
        ):
            mongo_store.read("test-namespace", "test-key")

    def test_read_operation_failure(self, mongo_store, mock_collection):
        """Test read with OperationFailure raises AccessError."""
        mock_collection.find_one.side_effect = OperationFailure(
            "Permission denied"
        )

        with pytest.raises(
            AccessError,
            match="Unable to access 'test-key' under 'test-namespace'",
        ):
            mongo_store.read("test-namespace", "test-key")

    def test_read_connection_failure(self, mongo_store, mock_collection):
        """Test read with ConnectionFailure raises StoreError."""
        mock_collection.find_one.side_effect = ConnectionFailure(
            "Connection lost"
        )

        with pytest.raises(
            StoreError,
            match="Unable to access store for 'test-key' under "
            "'test-namespace'",
        ):
            mongo_store.read("test-namespace", "test-key")

    def test_read_encryption_error(
        self, mongo_store, mock_collection, mock_client_encryption
    ):
        """Test read with EncryptionError raises StoreError."""
        encrypted_value = Binary(b"encrypted_data")
        mock_collection.find_one.return_value = {
            "key": "test-key",
            "value": encrypted_value,
        }
        mock_client_encryption.decrypt.side_effect = EncryptionError(
            "Decryption failed"
        )

        with pytest.raises(
            StoreError,
            match="Failed to decrypt value for 'test-key' under "
            "'test-namespace'",
        ):
            mongo_store.read("test-namespace", "test-key")

    def test_read_unicode_decode_error(
        self, mongo_store, mock_collection, mock_client_encryption
    ):
        """Test read with UnicodeDecodeError raises StoreError."""
        encrypted_value = Binary(b"encrypted_data")
        mock_collection.find_one.return_value = {
            "key": "test-key",
            "value": encrypted_value,
        }
        mock_client_encryption.decrypt.return_value = b"\xff\xfe"

        with pytest.raises(
            StoreError,
            match="Failed to decrypt value for 'test-key' under "
            "'test-namespace'",
        ):
            mongo_store.read("test-namespace", "test-key")

    def test_read_decrypt_none(
        self, mongo_store, mock_collection, mock_client_encryption
    ):
        """Test read when decrypt returns None raises StoreError."""
        encrypted_value = Binary(b"encrypted_data")
        mock_collection.find_one.return_value = {
            "key": "test-key",
            "value": encrypted_value,
        }
        mock_client_encryption.decrypt.return_value = None

        with pytest.raises(
            StoreError,
            match="Failed to decrypt value for 'test-key' under "
            "'test-namespace'",
        ):
            mongo_store.read("test-namespace", "test-key")

    def test_write_success(
        self, mongo_store, mock_collection, mock_client_encryption
    ):
        """Test successful secret write."""
        encrypted_value = Binary(b"encrypted_data")
        mock_client_encryption.encrypt.return_value = encrypted_value

        mongo_store.write("test-namespace", "test-key", "test-value")

        mock_client_encryption.encrypt.assert_called_once_with(
            value="test-value".encode("utf-8"),
            algorithm=mongo_store.algorithm,
            key_alt_name="test-key",
        )
        mock_collection.replace_one.assert_called_once_with(
            {"key": "test-key"},
            {"key": "test-key", "value": encrypted_value},
            upsert=True,
        )

    def test_write_encryption_error(
        self, mongo_store, mock_collection, mock_client_encryption
    ):
        """Test write with EncryptionError raises StoreError."""
        mock_client_encryption.encrypt.side_effect = EncryptionError(
            "Encryption failed"
        )

        with pytest.raises(
            StoreError,
            match="Failed to encrypt value for 'test-key' under "
            "'test-namespace'",
        ):
            mongo_store.write("test-namespace", "test-key", "test-value")

    def test_write_unicode_encode_error(
        self, mongo_store, mock_collection, mock_client_encryption
    ):
        """Test write with UnicodeEncodeError raises StoreError."""
        mock_client_encryption.encrypt.side_effect = UnicodeEncodeError(
            "utf-8", "", 0, 1, "Invalid encoding"
        )

        with pytest.raises(
            StoreError,
            match="Failed to encrypt value for 'test-key' under "
            "'test-namespace'",
        ):
            mongo_store.write("test-namespace", "test-key", "test-value")

    def test_write_operation_failure(
        self, mongo_store, mock_collection, mock_client_encryption
    ):
        """Test write with OperationFailure raises AccessError."""
        encrypted_value = Binary(b"encrypted_data")
        mock_client_encryption.encrypt.return_value = encrypted_value
        mock_collection.replace_one.side_effect = OperationFailure(
            "Permission denied"
        )

        with pytest.raises(
            AccessError,
            match="Unable to access 'test-key' under 'test-namespace'",
        ):
            mongo_store.write("test-namespace", "test-key", "test-value")

    def test_write_connection_failure(
        self, mongo_store, mock_collection, mock_client_encryption
    ):
        """Test write with ConnectionFailure raises StoreError."""
        encrypted_value = Binary(b"encrypted_data")
        mock_client_encryption.encrypt.return_value = encrypted_value
        mock_collection.replace_one.side_effect = ConnectionFailure(
            "Connection lost"
        )

        with pytest.raises(
            StoreError,
            match="Unable to access store for 'test-key' under "
            "'test-namespace'",
        ):
            mongo_store.write("test-namespace", "test-key", "test-value")

    def test_delete_success(self, mongo_store, mock_collection):
        """Test successful secret delete."""
        mongo_store.delete("test-namespace", "test-key")

        mock_collection.delete_one.assert_called_once_with({"key": "test-key"})

    def test_delete_operation_failure(self, mongo_store, mock_collection):
        """Test delete with OperationFailure raises AccessError."""
        mock_collection.delete_one.side_effect = OperationFailure(
            "Permission denied"
        )

        with pytest.raises(
            AccessError,
            match="Unable to access 'test-key' under 'test-namespace'",
        ):
            mongo_store.delete("test-namespace", "test-key")

    def test_delete_connection_failure(self, mongo_store, mock_collection):
        """Test delete with ConnectionFailure raises StoreError."""
        mock_collection.delete_one.side_effect = ConnectionFailure(
            "Connection lost"
        )

        with pytest.raises(
            StoreError,
            match="Unable to access store for 'test-key' under "
            "'test-namespace'",
        ):
            mongo_store.delete("test-namespace", "test-key")

    def test_delete_nonexistent_key(self, mongo_store, mock_collection):
        """Test delete of non-existent key succeeds silently."""
        mock_collection.delete_one.return_value.deleted_count = 0

        mongo_store.delete("test-namespace", "nonexistent-key")

        mock_collection.delete_one.assert_called_once_with(
            {"key": "nonexistent-key"}
        )

    def test_initialization(
        self, mock_client, mock_client_encryption, mock_database
    ):
        """Test MongoStore initialization."""
        mock_client.get_default_database.return_value = mock_database

        store = MongoStore(
            mock_client, mock_client_encryption, "test-data-key"
        )

        assert store.database == mock_database
        assert store.cipher == mock_client_encryption
        assert store.data_key_name == "test-data-key"

    def test_namespace_collection_access(
        self, mongo_store, mock_database, mocker
    ):
        """Test that namespaces create proper collection access."""
        namespace = "production"
        key = "api-key"

        mock_collection = mocker.Mock()
        mock_database.secrets.__getitem__ = mocker.Mock(
            return_value=mock_collection
        )
        mock_collection.find_one.return_value = None

        with pytest.raises(AccessError):
            mongo_store.read(namespace, key)

        mock_database.secrets.__getitem__.assert_called_with(namespace)
        mock_collection.find_one.assert_called_once_with({"key": key})


class TestSetupMongoStore:
    """Test cases for setup_mongo_store function."""

    @pytest.fixture
    def valid_master_key(self, mocker):
        """Set up valid master key in environment."""
        key = base64.b64encode(os.urandom(96)).decode("utf-8")
        mocker.patch.dict(
            "os.environ", {"TESTFLINGER_SECRETS_MASTER_KEY": key}, clear=True
        )
        return key

    @pytest.fixture
    def mock_mongo_setup(self, mocker):
        """Mock common setup for setup_mongo_store tests."""
        mocker.patch(
            "testflinger.secrets.get_mongo_uri",
            return_value="mongodb://localhost:27017/test",
        )

        mock_client = mocker.Mock(spec=MongoClient)
        mock_cipher = mocker.Mock(spec=ClientEncryption)
        mock_store = mocker.Mock(spec=MongoStore)

        mocker.patch(
            "testflinger.secrets.MongoClient", return_value=mock_client
        )
        mocker.patch(
            "testflinger.secrets.ClientEncryption", return_value=mock_cipher
        )
        mocker.patch("testflinger.secrets.MongoStore", return_value=mock_store)

        return mock_client, mock_cipher, mock_store

    @pytest.mark.parametrize(
        "env_vars",
        [
            {},
            {"TESTFLINGER_SECRETS_MASTER_KEY": ""},
            {"TESTFLINGER_SECRETS_MASTER_KEY": "invalid-base64!"},
        ],
    )
    def test_setup_mongo_store_error_cases(self, mocker, env_vars):
        """Test setup_mongo_store error cases."""
        mocker.patch.dict("os.environ", env_vars, clear=True)
        assert setup_mongo_store() is None

    def test_setup_mongo_store_success_with_existing_key(
        self, mocker, valid_master_key, mock_mongo_setup
    ):
        """Test successful setup when data encryption key already exists."""
        mock_client, mock_cipher, mock_store = mock_mongo_setup

        # Mock the key vault to return an existing key
        mock_key_vault = mocker.Mock()
        mock_key_vault.find_one.return_value = {"_id": "existing-key"}
        mock_database = mocker.Mock()
        mock_database.__getitem__ = mocker.Mock(return_value=mock_key_vault)
        mock_client.__getitem__ = mocker.Mock(return_value=mock_database)

        result = setup_mongo_store()

        # Verify key vault access
        mock_key_vault.find_one.assert_called_once_with(
            {"keyAltNames": "testflinger-secrets"}
        )

        # Verify no new key creation (existing key found)
        mock_cipher.create_data_key.assert_not_called()

        # Verify MongoStore creation
        assert result == mock_store

    def test_setup_mongo_store_success_with_new_key(
        self, mocker, valid_master_key, mock_mongo_setup
    ):
        """Test successful setup when creating new data encryption key."""
        mock_client, mock_cipher, mock_store = mock_mongo_setup

        # Mock the key vault to return no existing key
        mock_key_vault = mocker.Mock()
        mock_key_vault.find_one.return_value = None
        mock_database = mocker.Mock()
        mock_database.__getitem__ = mocker.Mock(return_value=mock_key_vault)
        mock_client.__getitem__ = mocker.Mock(return_value=mock_database)

        result = setup_mongo_store()

        # Verify new key creation
        mock_cipher.create_data_key.assert_called_once_with(
            "local", key_alt_names=["testflinger-secrets"]
        )

        # Verify MongoStore creation
        assert result == mock_store

    def test_setup_mongo_store_key_creation_error(
        self, mocker, valid_master_key, mock_mongo_setup
    ):
        """Test setup_mongo_store handles EncryptionError in key creation."""
        mock_client, mock_cipher, mock_store = mock_mongo_setup

        # Mock the key vault to return no existing key
        mock_key_vault = mocker.Mock()
        mock_key_vault.find_one.return_value = None
        mock_database = mocker.Mock()
        mock_database.__getitem__ = mocker.Mock(return_value=mock_key_vault)
        mock_client.__getitem__ = mocker.Mock(return_value=mock_database)

        # Mock cipher to raise EncryptionError on key creation
        mock_cipher.create_data_key.side_effect = EncryptionError(
            "Key creation failed"
        )

        with pytest.raises(
            StoreError,
            match="Failed to create data encryption key: Key creation failed",
        ):
            setup_mongo_store()
