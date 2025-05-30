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
    """Exception thrown when unable to retrieve status
    information from TF Server.
    """

    def __init__(self, endpoint: str) -> None:
        super().__init__(
            f"Unable to retrieve {endpoint} status from the server, check "
            "your connection or try again later."
        )
