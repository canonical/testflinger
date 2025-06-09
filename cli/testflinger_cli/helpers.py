# Copyright (C) 2025 Canonical Ltd.
"""Helpers for the Testflinger CLI."""

from os import getenv
from pathlib import Path
from typing import Optional

from testflinger_cli.consts import SNAP_NAME, SNAP_PRIVATE_DIRS
from testflinger_cli.errors import SnapPrivateFileError


def is_snap() -> bool:
    """Check if the current environment is in the Testflinger snap."""
    return getenv("SNAP_NAME") == SNAP_NAME


def file_is_in_snap_private_dir(file: Path) -> bool:
    """Check if the file is in a snap-private directory."""
    return any(
        file.resolve().is_relative_to(path) for path in SNAP_PRIVATE_DIRS
    )


def parse_filename(
    filename: str,
    parse_stdin: bool = False,
    check_snap_private_dir: bool = True,
) -> Optional[Path]:
    """Parse the filename and return a Path object.

    :param filename:
        The filename to parse.
    :param parse_stdin:
        If True, treat "-" as stdin.
    :param check_snap_private_dir:
        If True, check if the file is in a snap-private directory.
    :return:
        A Path object representing the filename. None if parse_stdin is True
        and filename is "-".
    :raises SnapPrivateFileError:
        If the file is in a snap-private directory
        and check_snap_private_dir is True.
    """
    if parse_stdin and filename == "-":
        return None
    path = Path(filename)
    if (
        check_snap_private_dir
        and is_snap()
        and file_is_in_snap_private_dir(path)
    ):
        raise SnapPrivateFileError(path)
    return path


def prompt_for_image(images: dict[str, str]) -> str:
    """Prompt the user to select an image from a list.

    :param images: A mapping of image name to image job line to choose from.
    :return: The selected image.
    """
    input_msg = "\nEnter the image you wish to use"
    if images and any(value.startswith("url:") for value in images.values()):
        input_msg += " or a URL for a valid image, starting with http(s)://"
    input_msg += " ('?' to list): "
    image = ""
    while not image:
        image = input(input_msg).strip()
        if not image:
            continue
        if image == "?":
            if not images:
                print(
                    "WARNING: No images defined for this device. You may also "
                    "provide the URL to an image that can be booted with this "
                    "device though."
                )
            else:
                print("\n".join(sorted(images)))
            image = ""
        elif image.startswith(("http://", "https://")):
            return image
        elif image not in images:
            print(
                f"ERROR: '{image}' is not in the list of known images for "
                "that queue, please select another."
            )
            image = ""
    return image


def prompt_for_ssh_keys() -> list[str]:
    """Prompt the user to select SSH keys.

    :return: A list of SSH keys in the form of gh:user or lp:user.
    """
    input_msg = "\nEnter the key(s) you wish to use (ex: 'lp:user,gh:user'): "
    ssh_keys: list[str] = []
    while not ssh_keys:
        keys = input(input_msg).strip()
        if not keys:
            continue
        ssh_keys = [key.strip() for key in keys.split(",")]
        if not all(key.startswith(("gh:", "lp:")) for key in ssh_keys):
            print("Please enter keys in the form of 'gh:user' or 'lp:user'.")
            ssh_keys = []
    return ssh_keys


def prompt_for_queue(queues: dict[str, str]) -> str:
    """Prompt the user to select a queue from a list.

    :param queues: A mapping of queue name to descripton to choose from.
    :return: The selected queue.
    """
    input_msg = "\nEnter the queue you wish to use ('?' to list): "
    queue = ""
    while not queue:
        queue = input(input_msg).strip()
        if not queue:
            continue
        if queue == "?":
            print("\nAdvertised queues on this server:")
            for name, description in queues.items():
                print(f" {name} - {description}")
            queue = ""
        elif queue not in queues:
            print(f"WARNING: '{queue}' is not in the list of known queues")
            answer = input("Do you still want to use it? (y/N) ").strip()
            if answer.lower() != "y":
                queue = ""
    return queue
