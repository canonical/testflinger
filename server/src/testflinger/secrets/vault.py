"""Ref: https://python-hvac.org/en/stable/source/hvac_exceptions.html#module-hvac.exceptions."""

import hvac

from testflinger.secrets.exceptions import (
    AccessError,
    StoreError,
    UnexpectedError,
)
from testflinger.secrets.store import SecretsStore


class VaultStore(SecretsStore):
    hvac_access_errors = (
        hvac.exceptions.Forbidden,
        hvac.exceptions.InvalidPath,
        hvac.exceptions.Unauthorized,
    )

    def __init__(self, client: hvac.Client):
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
        except hvac.exceptions.VaultError as error:
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

    def write(self, namespace: str, key: str, value: str) -> bool:
        """Write the `value` for `key` under `namespace`."""
        # write (or update) the secret value using the Vault API
        try:
            self.client.secrets.kv.v2.create_or_update_secret(
                path=f"{namespace}/{key}", secret={"value": value}
            )
        except self.hvac_access_errors as error:
            raise AccessError(
                f"Unable to access '{key}' under '{namespace}'"
            ) from error
        except hvac.exceptions.VaultError as error:
            raise StoreError(
                f"Unable to access store for '{key}' under '{namespace}'"
            ) from error

    def delete(self, namespace: str, key: str):
        """Delete the value for `key` under `namespace`, if any."""
        # delete the secret value using the Vault API
        try:
            self.client.secrets.kv.v2.delete_metadata_and_all_versions(
                path=key
            )
        except hvac.exceptions.InvalidPath:
            # no failure if the secret does not exist
            pass
        except self.hvac_access_errors as error:
            raise AccessError(
                f"Unable to access '{key}' under '{namespace}'"
            ) from error
        except hvac.exceptions.VaultError as error:
            raise StoreError(
                f"Unable to access store for '{key}' under '{namespace}'"
            ) from error
