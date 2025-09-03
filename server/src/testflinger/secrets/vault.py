import hvac

from testflinger.secrets.store import SecretsStore, SecretAccessError


class VaultStore(SecretsStore):

    def __init__(self, client: hvac.Client):
        self.client = client

    def read(self, user: str, key: str) -> str:
        # retrieve the corresponding entry from the Vault API
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=f"{user}/{key}"
            )
        except (
            hvac.exceptions.InvalidPath,
            hvac.exceptions.Forbidden,
            hvac.exceptions.Unauthorized,
        ) as error:
            raise SecretAccessError(
                f"Unable to access '{key}' for user '{user}'"
            ) from error
        # retrieve the secret value from the entry and return it
        try:
            return response['data']['data']['value']
        except KeyError as error:
            raise SecretAccessError(
                f"Unable to access '{key}' for user '{user}'"
            ) from error

    def write(self, user: str, key: str, value: str) -> bool:
        # write (or update) the secret value using the Vault API
        try:
            self.client.secrets.kv.v2.create_or_update_secret(
                path=f"{user}/{key}",
                secret={'value': value}
            )
        except (hvac.exceptions.Forbidden, hvac.exceptions.Unauthorized) as error:
            raise SecretAccessError(
                f"Unable to modify '{key}' for user '{user}'"
            ) from error

    def delete(self, user: str, key: str):
        # delete the secret value using the Vault API
        try:
            self.client.secrets.kv.v2.delete_metadata_and_all_versions(
                path=key,
                mount_point=self.mount_point
            )
        except hvac.exceptions.InvalidPath:
            # no failure if the secret does not exist
            pass
        except (hvac.exceptions.Forbidden, hvac.exceptions.Unauthorized) as error:
            raise SecretAccessError(
                f"Unable to modify '{key}' for user '{user}'"
            ) from error
