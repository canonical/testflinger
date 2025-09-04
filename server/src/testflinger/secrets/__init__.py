from hvac import Client
import os

from testflinger.secrets.exceptions import StoreError
from testflinger.secrets.store import SecretsStore
from testflinger.secrets.vault import VaultStore


def setup_secrets_store() -> SecretsStore | None:
    """
    Create and return a store for secrets, if possible.

    Currently, the store returned is an instance of `VaultStore`.

    Not setting up a secrets store is not an error: it just means that
    Testflinger jobs will not be able to use secrets.
    """
    vault_url = os.environ.get("TESTFLINGER_VAULT_URL")
    vault_token = os.environ.get("TESTFLINGER_VAULT_TOKEN")
    if not vault_url or not vault_token:
        return None

    client = Client(url=vault_url, token=vault_token)
    if not client.is_authenticated():
        raise StoreError("Vault client not authenticated")

    return VaultStore(client)
