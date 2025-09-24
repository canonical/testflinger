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

"""Default setup for the Testflinger secrets store."""

import os

import requests
from hvac import Client

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
    try:
        if not client.is_authenticated():
            raise StoreError("Vault client not authenticated")
    except requests.exceptions.ConnectionError as error:
        raise StoreError("Unable to create Vault client") from error

    return VaultStore(client)
