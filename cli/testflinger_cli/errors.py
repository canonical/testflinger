# Copyright (C) 2025 Canonical Ltd.
"""Custom errors for Testflinger CLI."""

from os import PathLike


class AttachmentError(Exception):
    """Exception thrown when attachments fail to be submitted."""


class SnapPrivateFileError(FileNotFoundError):
    """Exception thrown when a file is not found due to snap confinement."""

    def __init__(self, path: PathLike[str]) -> None:
        """Initialize the SnapPrivateFileError.

        :param path: The path of the file that is in a snap-private directory.
        """
        super().__init__(f"File {path} is in a snap-private directory.")


class UnknownStatusError(Exception):
    """Exception thrown when unable to retrieve a status from the server."""

    def __init__(self, endpoint: str) -> None:
        super().__init__(
            f"Unable to retrieve {endpoint} status from the server, check "
            "your connection or try again later."
        )


class AuthenticationError(Exception):
    """Exception thrown when unable to authenticate with the server."""

    def __init__(self) -> None:
        super().__init__(
            "Authentication with Testflinger server failed. "
            "Check your client id and secret key"
        )


class AuthorizationError(Exception):
    """Exception thrown when unable to get correct authorization
    for sending request to the server.
    """

    def __init__(self) -> None:
        super().__init__(
            "Authorization error received from server. \n"
            "Make sure you are connected to the right network or "
            "contact Testflinger admin for more information"
        )
