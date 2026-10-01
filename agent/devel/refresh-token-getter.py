#!/usr/bin/env python3
"""Obtain a development agent refresh token from a Testflinger server."""

import argparse
import base64
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# These match the entries in server/devel/sample_users.py
CLIENT_ID = "testflinger-agent"
CLIENT_SECRET = "testflinger"  # noqa: S105


def main():
    """Request and write a refresh token for the generic development agent."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("server_url")
    parser.add_argument("token_file", type=Path, nargs='?',
                        default="devel/.testflinger/refresh_token")
    args = parser.parse_args()

    credentials = base64.b64encode(
        f"{CLIENT_ID}:{CLIENT_SECRET}".encode()
    ).decode()
    request = Request(  # noqa: S310
        f"{args.server_url.rstrip('/')}/v1/oauth2/token",
        headers={"Authorization": f"Basic {credentials}"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:  # noqa: S310
            token_data = json.load(response)
    except (HTTPError, URLError) as exc:
        parser.error(f"could not obtain a development agent token: {exc}")

    if not token_data.get("refresh_token"):
        parser.error("server response did not contain a refresh token")

    args.token_file.parent.mkdir(parents=True, exist_ok=True)
    args.token_file.write_text(json.dumps(token_data))
    print(f"Refresh token written to {args.token_file}")


if __name__ == "__main__":
    main()
