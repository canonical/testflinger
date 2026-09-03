"""Testflinger CLI entry point."""

import os
from typing import Annotated

import typer

from testflinger_cli import client, consts
from testflinger_cli.auth import TestflingerCliAuth
from testflinger_cli.commands import jobs, results

tf_cli = typer.Typer()
tf_cli.add_typer(results.results_subcommands)
tf_cli.add_typer(jobs.jobs_subcommands)


@tf_cli.callback()
def main(
    ctx: typer.Context,
    server: Annotated[
        str,
        typer.Option(
            "--server",
            help="Testflinger server URL.",
        ),
    ] = consts.TESTFLINGER_SERVER,
    client_id: Annotated[
        str,
        typer.Option(
            "--client-id",
            help="Testflinger client ID.",
        ),
    ] = os.environ.get("TESTFLINGER_CLIENT_ID"),
    client_secret: Annotated[
        str,
        typer.Option(
            "--client-secret",
            help="Testflinger client secret.",
        ),
    ] = os.environ.get("TESTFLINGER_CLIENT_SECRET"),
):
    """Canonical Testflinger CLI."""
    auth_manager = TestflingerCliAuth(
        client_id=client_id,
        secret_key=client_secret,
        server_url=server,
    )
    ctx.obj = client.Client(server=server, auth_manager=auth_manager)


if __name__ == "__main__":
    tf_cli()
