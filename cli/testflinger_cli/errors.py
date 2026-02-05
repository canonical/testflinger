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


class NoJobDataError(Exception):
    """Exception thrown when job has no data (HTTP 204 No Content)."""

    def __init__(self) -> None:
        super().__init__(
            "No data found for that job id. Check the "
            "job id to be sure it is correct"
        )


class InvalidJobIdError(Exception):
    """Exception thrown when job id is invalid (HTTP 400 Bad Request)."""

    def __init__(self) -> None:
        super().__init__(
            "Invalid job id specified. Check the job id "
            "to be sure it is correct"
        )


class CredentialsError(Exception):
    """Base class for errors related to authentication and authorization."""


class AuthenticationError(CredentialsError):
    """Exception thrown when unable to authenticate with the server."""

    def __init__(self) -> None:
        super().__init__(
            "Authentication with Testflinger server failed. "
            "Check your client id and secret key"
        )


class AuthorizationError(CredentialsError):
    """Exception thrown when unable to get correct authorization
    for sending request to the server.
    """

    def __init__(self, reason: str | None = None) -> None:
        default_reason = (
            "Authorization error received from server. \n"
            "Make sure you are connected to the right network or "
            "contact Testflinger admin for more information"
        )
        self.message = reason or default_reason

    def __str__(self) -> str:
        """Return a string with the the error message."""
        return self.message


class InvalidTokenError(CredentialsError):
    """Exception thrown when refresh token is missing, invalid,
    revoked or expired.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(
            "Authentication with Testflinger server failed with "
            f"following reason: {reason} "
            "Please reauthenticate with server."
        )


class NetworkError(Exception):
    """Exception thrown when unable to communicate with server."""


class VPNError(NetworkError):
    """Exception for when a VPN connection is required but not established."""

    def __init__(self) -> None:
        super().__init__(
            "403 Forbidden Error: Server access requires a VPN connection.\n"
            "Please make sure you are connected to the VPN and try again."
        )
