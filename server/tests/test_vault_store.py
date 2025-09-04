import hvac
import pytest

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

    def test_delete_success(self, vault_store, mock_client):
        """Test successful secret delete."""
        vault_store.delete("test-namespace", "test-key")
        mock_client.secrets.kv.v2.delete_metadata_and_all_versions.assert_called_once_with(
            path="test-key"
        )

    def test_delete_invalid_path_ignored(self, vault_store, mock_client):
        """Test delete with InvalidPath error is ignored."""
        mock_client.secrets.kv.v2.delete_metadata_and_all_versions.side_effect = hvac.exceptions.InvalidPath()
        vault_store.delete("test-namespace", "test-key")
        mock_client.secrets.kv.v2.delete_metadata_and_all_versions.assert_called_once_with(
            path="test-key"
        )
