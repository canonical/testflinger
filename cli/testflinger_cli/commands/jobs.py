"""Commands for interacting with jobs."""

import json
import logging
import sys
from enum import Enum
from http import HTTPStatus
from typing import Annotated

import typer

from testflinger_cli import client, errors, helpers

logger = logging.getLogger(__name__)

jobs_subcommands = typer.Typer()


class FormatOption(str, Enum):
    """Enum for output format options."""

    JSON = "json"
    YAML = "yaml"


@jobs_subcommands.command()
def show(
    ctx: typer.Context,
    job_id: str,
    output_format: Annotated[
        FormatOption,
        typer.Option(
            "--format",
            help="Output format (json or yaml).",
        ),
    ] = FormatOption.YAML,
):
    """Show details of a specific job."""
    tf_client: client.Client = ctx.obj

    try:
        results = tf_client.get_job_data(job_id)
    except errors.NoJobDataError:
        sys.exit("No data found for that job id.")
    except errors.InvalidJobIdError:
        sys.exit(
            "Invalid job id specified. Check the job id "
            "to be sure it is correct"
        )
    except client.HTTPError as exc:
        sys.exit(exc.msg)

    if output_format == FormatOption.YAML:
        to_print = helpers.pretty_yaml_dump(
            results, sort_keys=True, indent=4, default_flow_style=False
        )
    else:
        to_print = json.dumps(results, sort_keys=True, indent=4)
    print(to_print)


@jobs_subcommands.command()
def job_status(
    ctx: typer.Context,
    job_id: str,
):
    """Show the status of a specific job."""
    tf_client: client.Client = ctx.obj

    try:
        job_state = get_job_state(tf_client, job_id)["job_state"]
        if job_state != "unknown":
            print(job_state)
        else:
            print(
                "Unable to retrieve job state from the server, check your "
                "connection or try again later."
            )
    except (errors.NoJobDataError, errors.InvalidJobIdError) as exc:
        sys.exit(str(exc))


def get_job_state(tf_client, job_id: str) -> dict:
    """Return the job state for the specified job_id.

    :param tf_client: Testflinger client instance
    :param job_id: Job ID
    :raises NoJobDataError: When HTTP 204 (no data found)
    :raises InvalidJobIdError: When HTTP 400 (invalid job ID)
    :raises IOError: When network error occurs
    :raises ValueError: When response cannot be parsed
    :return: Job and phase statuses
    """
    try:
        return tf_client.get_status(job_id)
    except client.HTTPError as exc:
        if exc.status == HTTPStatus.NO_CONTENT:
            raise errors.NoJobDataError from exc
        if exc.status == HTTPStatus.BAD_REQUEST:
            raise errors.InvalidJobIdError from exc
        # For other HTTP errors, log and return unknown state
        logger.debug("HTTP error retrieving job state: %s", exc)
    except (IOError, ValueError) as exc:
        # For other types of network errors, or JSONDecodeError if we got
        # a bad return from get_status()
        logger.debug("Unable to retrieve job state: %s", exc)
    return {"job_state": "unknown"}
