from abc import ABC, abstractmethod


class SecretsError(Exception):
    pass


class SecretAccessError(SecretsError):
    pass


class SecretsStore(ABC):

    @abstractmethod
    def read(self, user: str, key: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def write(self, user: str, key: str, value: str):
        raise NotImplementedError

    @abstractmethod
    def delete(self, user: str, key: str):
        raise NotImplementedError
