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

"""A Vault-based implementation for the Testflinger secrets store."""

import hvac
import requests

from testflinger.secrets.exceptions import (
    AccessError,
    StoreError,
    UnexpectedError,
)
from testflinger.secrets.store import DEFAULT_SECRET_EXPIRATION, SecretsStore


class VaultStore(SecretsStore):
    """A Vault-based secrets store implementation."""

    # this collection of errors leads to an AccessError being raised
    hvac_access_errors = (
        hvac.exceptions.Forbidden,
        hvac.exceptions.InvalidPath,
        hvac.exceptions.Unauthorized,
    )

    def __init__(self, client: hvac.Client):
        """Initialize the store with a Vault client."""
        self.client = client

    def read(self, namespace: str, key: str) -> str:
        """Return the stored value for `key` under `namespace`."""
        # read the corresponding entry from the Vault API
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=f"{namespace}/{key}"
            )
        except self.hvac_access_errors as error:
            raise AccessError(
                f"Unable to access '{key}' under '{namespace}'"
            ) from error
        except (
            hvac.exceptions.VaultError,
            requests.exceptions.ConnectionError,
        ) as error:
            raise StoreError(
                f"Unable to access store for '{key}' under '{namespace}'"
            ) from error
        # retrieve the secret value from the entry and return it
        try:
            return response["data"]["data"]["value"]
        except KeyError as error:
            raise UnexpectedError(
                f"Unable to process response for '{key}' under '{namespace}'"
            ) from error

    def write(
        self,
        namespace: str,
        key: str,
        value: str,
        expire_after: int | None = DEFAULT_SECRET_EXPIRATION,
        ephemeral: bool = False,
    ) -> bool:
        """Write the `value` for `key` under `namespace`.

        :param namespace: the namespace under which to store the secret
        :param key: the key for the secret
        :param value: the value of the secret to store
        :param expire_after: Expiration time in seconds for the secret.
        :param ephemeral: whether the secret should be deleted after being read
        :returns: True if the secret was successfully stored, False otherwise
        """
        # write (or update) the secret value using the Vault API
        try:
            self.client.secrets.kv.v2.create_or_update_secret(
                path=f"{namespace}/{key}", secret={"value": value}
            )
        except self.hvac_access_errors as error:
            raise AccessError(
                f"Unable to access '{key}' under '{namespace}'"
            ) from error
        except (
            hvac.exceptions.VaultError,
            requests.exceptions.ConnectionError,
        ) as error:
            raise StoreError(
                f"Unable to access store for '{key}' under '{namespace}'"
            ) from error

    def delete(self, namespace: str, key: str):
        """Delete the value for `key` under `namespace`, if any."""
        # delete the secret value using the Vault API
        try:
            self.client.secrets.kv.v2.delete_metadata_and_all_versions(
                path=f"{namespace}/{key}"
            )
        except hvac.exceptions.InvalidPath:
            # no failure if the secret does not exist
            pass
        except self.hvac_access_errors as error:
            raise AccessError(
                f"Unable to access '{key}' under '{namespace}'"
            ) from error
        except (
            hvac.exceptions.VaultError,
            requests.exceptions.ConnectionError,
        ) as error:
            raise StoreError(
                f"Unable to access store for '{key}' under '{namespace}'"
            ) from error

    def exists(self, namespace: str, key: str) -> bool:
        """Check if the `key` exists under `namespace`.

        :param namespace: The namespace to check for the secret.
        :param key: The key for the secret to check.
        :returns: True if the secret exists, False otherwise.
        """
        # read the corresponding entry from the Vault API
        try:
            return (
                self.client.secrets.kv.v2.read_secret_version(
                    path=f"{namespace}/{key}"
                )
                is not None
            )
        except (
            *self.hvac_access_errors,
            hvac.exceptions.VaultError,
            requests.exceptions.ConnectionError,
        ):
            return False
