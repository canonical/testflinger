from abc import ABC, abstractmethod


class SecretsStore(ABC):
    """
    Classes derived from this abstract base class implement the interface
    for a secrets store, i.e. an entity that can securely read, write and
    delete key-value pairs under different namespaces.

    All class methods are expected to raise an appropriate instance of
    testflinger.secrets.exceptions.SecretsError if they encounter an issue.
    """

    @abstractmethod
    def read(self, namespace: str, key: str) -> str:
        """Return the stored value for `key` under `namespace`."""
        raise NotImplementedError

    @abstractmethod
    def write(self, namespace: str, key: str, value: str):
        """Write the `value` for `key` under `namespace`."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, namespace: str, key: str):
        """Delete the value for `key` under `namespace`, if any."""
        raise NotImplementedError
