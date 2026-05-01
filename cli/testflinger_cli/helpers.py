# Copyright (C) 2025 Canonical Ltd.
"""Helpers for the Testflinger CLI."""

import argparse
import re
from datetime import datetime
from os import getenv
from pathlib import Path
from typing import Optional

import yaml

from testflinger_cli.consts import SNAP_NAME, SNAP_PRIVATE_DIRS
from testflinger_cli.errors import SnapPrivateFileError

# Only accept paths that are separated by forward slashes
# Expected format should not start or end with a slash
# Examples of valid paths: "path", "my/secret/path"
PATH_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+(?:\/[a-zA-Z0-9_-]+)*$")


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


def prompt_for_image(images: dict[str, str]) -> str | None:
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
            choice = "x"
            while choice not in "yn":
                choice = (
                    input(
                        "\nNo image specified, proceed with no provision data?"
                        " (Y)es/(n)o? "
                    )
                    + "x"
                )[0].lower()  # dummy character to make indexing robust
            if choice == "y":
                return None
            continue
        elif image == "?":
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
        else:
            image = images[image].split("url:")[-1]
    return image.strip()


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


def multiline_str_representer(dumper, data):
    """
    Render multiline strings as blocks, leave other strings unchanged.

    This is a custom YAML representer for strings.
    """
    # see section "Constructors, representers resolvers"
    # at https://pyyaml.org/wiki/PyYAMLDocumentation
    # and https://yaml.org/spec/1.2.2/#literal-style
    if "\n" in data:
        # remove trailing whitespace from each line
        # (suggested fix for https://github.com/yaml/pyyaml/issues/240)
        data = "\n".join(line.rstrip() for line in data.splitlines()) + "\n"
        return dumper.represent_scalar(
            "tag:yaml.org,2002:str", data, style="|"
        )
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


yaml.add_representer(str, multiline_str_representer)


def pretty_yaml_dump(obj, **kwargs) -> str:
    """Create a pretty YAML representation of obj.

    :param obj: The object to be represented.
    :return: A pretty representation of obj as a YAML string.
    """
    return yaml.dump(obj, **kwargs)


def format_timestamp(timestamp_str: str) -> str:
    """Format timestamp for human reading.

    :param timestamp_str: ISO format timestamp string
    :return: Formatted timestamp string or original if parsing fails
    """
    if not timestamp_str:
        return "Unknown"

    try:
        # Parse ISO format timestamp
        dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, AttributeError):
        return timestamp_str


def parse_comma_list(choices: tuple | list[str]) -> callable:
    """Create a comma-separated list parser.

    :param choices: List of valid choices for each item in the
        comma-separated list.
    :return: A parser function that accepts comma-separated input and
        returns a list of validated strings.
    """

    def _parse_comma_list(arg: str) -> list[str]:
        value_list = [item.strip() for item in arg.split(",")]
        for item in value_list:
            if item not in choices:
                raise argparse.ArgumentTypeError(
                    f"invalid choice: '{item}' (choose from "
                    f"{', '.join(choices)})"
                )
        return value_list

    return _parse_comma_list


def regex_arg(value):
    """Compile and validate a regex pattern argument.

    :param value: The regex pattern string to compile
    :return: Compiled regex pattern
    :raises ArgumentTypeError: If the regex pattern is invalid
    """
    try:
        return re.compile(value)
    except re.error as err:
        raise argparse.ArgumentTypeError(
            f"Invalid regex '{value}', error: {str(err)}"
        ) from err


def regex_path(value, pattern: re.Pattern = PATH_PATTERN):
    """Validate that a file path argument is a valid regex pattern.

    :param value: The file path string to validate
    :param pattern: The regex pattern to validate against
    :return: The original value if valid
    :raises ArgumentTypeError: If the value does not match the regex pattern
    """
    if not pattern.match(value):
        raise argparse.ArgumentTypeError(
            f"Invalid value '{value}', not a valid path. \n"
            "Paths must only contain alphanumeric characters, hyphens (-), "
            "underscores (_), and forward slashes (/). Additionally, "
            "paths must not start or end with a forward slash (/)."
        )
    return value
