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

"""Tests for the Vault-based implementation of the secrets store."""

import hvac
import pytest
import requests.exceptions

from testflinger.secrets import setup_secrets_store, setup_vault_store
from testflinger.secrets.exceptions import (
    AccessError,
    StoreError,
    UnexpectedError,
)
from testflinger.secrets.vault import VaultStore


class TestVaultStore:
    """Test cases for VaultStore class."""

    @pytest.fixture
    def mock_client(self, mocker):
        """Mock hvac client."""
        return mocker.Mock(spec=hvac.Client)

    @pytest.fixture
    def vault_store(self, mock_client):
        """VaultStore instance with mocked client."""
        return VaultStore(mock_client)

    def test_read_success(self, vault_store, mock_client):
        """Test successful secret read."""
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"value": "test-secret-value"}}
        }

        result = vault_store.read("test-namespace", "test-key")

        assert result == "test-secret-value"
        mock_client.secrets.kv.v2.read_secret_version.assert_called_once_with(
            path="test-namespace/test-key"
        )

    @pytest.mark.parametrize("error_cls", VaultStore.hvac_access_errors)
    def test_read_error(self, error_cls, vault_store, mock_client):
        """Test read with error raises AccessError."""
        mock_client.secrets.kv.v2.read_secret_version.side_effect = error_cls()

        with pytest.raises(AccessError):
            vault_store.read("test-namespace", "test-key")

    def test_read_vault_error(self, vault_store, mock_client):
        """Test read with VaultError raises StoreError."""
        mock_client.secrets.kv.v2.read_secret_version.side_effect = (
            hvac.exceptions.VaultError()
        )

        with pytest.raises(StoreError):
            vault_store.read("test-namespace", "test-key")

    def test_read_connection_error(self, vault_store, mock_client):
        """Test read with ConnectionError raises StoreError."""
        mock_client.secrets.kv.v2.read_secret_version.side_effect = (
            requests.exceptions.ConnectionError()
        )

        with pytest.raises(StoreError):
            vault_store.read("test-namespace", "test-key")

    def test_read_missing_data_key(self, vault_store, mock_client):
        """Test read with missing nested 'data' key raises UnexpectedError."""
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {}
        }

        with pytest.raises(UnexpectedError):
            vault_store.read("test-namespace", "test-key")

    def test_write_success(self, vault_store, mock_client):
        """Test successful secret write."""
        vault_store.write("test-namespace", "test-key", "test-value")

        mock_client.secrets.kv.v2.create_or_update_secret.assert_called_once_with(
            path="test-namespace/test-key", secret={"value": "test-value"}
        )

    @pytest.mark.parametrize("error_cls", VaultStore.hvac_access_errors)
    def test_write_error(self, error_cls, vault_store, mock_client):
        """Test write with error raises AccessError."""
        mock_client.secrets.kv.v2.create_or_update_secret.side_effect = (
            error_cls()
        )
        with pytest.raises(AccessError):
            vault_store.write("test-namespace", "test-key", "test-value")

    def test_write_vault_error(self, vault_store, mock_client):
        """Test write with VaultError raises StoreError."""
        mock_client.secrets.kv.v2.create_or_update_secret.side_effect = (
            hvac.exceptions.VaultError()
        )
        with pytest.raises(StoreError):
            vault_store.write("test-namespace", "test-key", "test-value")

    def test_write_connection_error(self, vault_store, mock_client):
        """Test write with ConnectionError raises StoreError."""
        mock_client.secrets.kv.v2.create_or_update_secret.side_effect = (
            requests.exceptions.ConnectionError()
        )
        with pytest.raises(StoreError):
            vault_store.write("test-namespace", "test-key", "test-value")

    def test_delete_success(self, vault_store, mock_client):
        """Test successful secret delete."""
        vault_store.delete("test-namespace", "test-key")
        mock_client.secrets.kv.v2.delete_metadata_and_all_versions.assert_called_once_with(
            path="test-namespace/test-key"
        )

    @pytest.mark.parametrize(
        "error_cls", [hvac.exceptions.Forbidden, hvac.exceptions.Unauthorized]
    )
    def test_delete_error(self, error_cls, vault_store, mock_client):
        """Test delete with error raises AccessError."""
        mock_client.secrets.kv.v2.delete_metadata_and_all_versions.side_effect = error_cls()  # noqa: E501

        with pytest.raises(AccessError):
            vault_store.delete("test-namespace", "test-key")

    def test_delete_vault_error(self, vault_store, mock_client):
        """Test delete with VaultError raises StoreError."""
        mock_client.secrets.kv.v2.delete_metadata_and_all_versions.side_effect = hvac.exceptions.VaultError()  # noqa: E501

        with pytest.raises(StoreError):
            vault_store.delete("test-namespace", "test-key")

    def test_delete_connection_error(self, vault_store, mock_client):
        """Test delete with ConnectionError raises StoreError."""
        mock_client.secrets.kv.v2.delete_metadata_and_all_versions.side_effect = requests.exceptions.ConnectionError()  # noqa: E501

        with pytest.raises(StoreError):
            vault_store.delete("test-namespace", "test-key")

    def test_delete_invalid_path_ignored(self, vault_store, mock_client):
        """Test delete with InvalidPath error is ignored."""
        mock_client.secrets.kv.v2.delete_metadata_and_all_versions.side_effect = hvac.exceptions.InvalidPath()  # noqa: E501
        vault_store.delete("test-namespace", "test-key")
        mock_client.secrets.kv.v2.delete_metadata_and_all_versions.assert_called_once_with(
            path="test-namespace/test-key"
        )


class TestSecretsInit:
    """Test cases for secrets module initialization."""

    @pytest.mark.parametrize(
        "env_vars",
        [
            {},  # no environment variables
            {"TESTFLINGER_VAULT_TOKEN": "token"},  # missing URL
            {"TESTFLINGER_VAULT_URL": "http://vault"},  # missing token
        ],
    )
    def test_setup_secrets_store_missing_config(self, mocker, env_vars):
        """Test setup_vault_store returns None when config is incomplete."""
        # Given: incomplete environment configuration
        mocker.patch.dict("os.environ", env_vars, clear=True)

        # When: setup_secrets_store is called
        result = setup_vault_store()

        # Then: it returns None
        assert result is None

    def test_setup_secrets_store_success(self, mocker):
        """Test successful setup_secrets_store."""
        # Given: environment variables are set and client is authenticated
        token = "token"  # noqa: S105
        mocker.patch.dict(
            "os.environ",
            {
                "TESTFLINGER_VAULT_URL": "http://vault",
                "TESTFLINGER_VAULT_TOKEN": token,
            },
            clear=True,
        )
        mock_client_instance = mocker.Mock(spec=hvac.Client)
        mock_client_instance.is_authenticated.return_value = True
        mock_client_class = mocker.patch(
            "testflinger.secrets.Client", return_value=mock_client_instance
        )

        # When: setup_secrets_store is called
        result = setup_secrets_store()

        # Then: it returns a VaultStore instance and creates client correctly
        assert isinstance(result, VaultStore)
        mock_client_class.assert_called_once_with(
            url="http://vault", token=token
        )

    def test_setup_vault_store_not_authenticated(self, mocker):
        """
        Test setup_vault_store raises StoreError when the client is not
        properly authenticated.
        """
        # Given: environment variables are set but client is not authenticated
        mocker.patch.dict(
            "os.environ",
            {
                "TESTFLINGER_VAULT_URL": "http://vault",
                "TESTFLINGER_VAULT_TOKEN": "token",
            },
            clear=True,
        )
        mock_client_instance = mocker.Mock(spec=hvac.Client)
        mock_client_instance.is_authenticated.return_value = False
        mocker.patch(
            "testflinger.secrets.Client", return_value=mock_client_instance
        )

        # When: setup_secrets_store is called
        # Then: it raises StoreError about authentication
        with pytest.raises(StoreError, match="Vault client not authenticated"):
            setup_vault_store()

    def test_setup_secrets_store_connection_error(self, mocker):
        """Test setup_secrets_store raises StoreError on ConnectionError."""
        # Given: environment variables are set but connection fails
        mocker.patch.dict(
            "os.environ",
            {
                "TESTFLINGER_VAULT_URL": "http://vault",
                "TESTFLINGER_VAULT_TOKEN": "token",
            },
            clear=True,
        )
        mock_client_instance = mocker.Mock(spec=hvac.Client)
        mock_client_instance.is_authenticated.side_effect = (
            requests.exceptions.ConnectionError()
        )
        mocker.patch(
            "testflinger.secrets.Client", return_value=mock_client_instance
        )

        # When: setup_secrets_store is called
        # Then: it raises StoreError about unable to create client
        with pytest.raises(StoreError, match="Vault client unable to connect"):
            setup_vault_store()
