"""Commands for interacting with results."""

import json
import logging
import sys
from http import HTTPStatus

import typer

from testflinger_cli import client

logger = logging.getLogger(__name__)

results_subcommands = typer.Typer()


@results_subcommands.command()
def get_results(ctx: typer.Context, job_id: str):
    """Get results JSON for a complete JOB_ID."""
    tf_client: client.Client = ctx.obj

    try:
        results = tf_client.get_results(job_id)
    except client.HTTPError as exc:
        if exc.status == HTTPStatus.NO_CONTENT:
            sys.exit("No results found for that job id.")
        if exc.status == HTTPStatus.NOT_FOUND:
            sys.exit(
                "Invalid job id specified. Check the job id "
                "to be sure it is correct"
            )
        # This shouldn't happen, so let's get more information
        logger.error(
            "Unexpected error status from testflinger server: %s",
            exc.status,
        )
        sys.exit(1)

    print(json.dumps(results, sort_keys=True, indent=4))
