import os
from hvac import Client

from testflinger.secrets.store import SecretsStore
from testflinger.secrets.vault import VaultStore


def setup_secrets_store() -> SecretsStore:
    vault_url = os.environ.get("TESTFLINGER_VAULT_URL")
    vault_token = os.environ.get("TESTFLINGER_VAULT_TOKEN")
    client = Client(url=vault_url, token=vault_token)
    return VaultStore(client)
