#!/usr/bin/env python3
# Copyright (C) 2026 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Generate or validate the permissions matrix for Testflinger API endpoints.

This script derives the permissions matrix from the OpenAPI spec produced by
generate_openapi_schema.py, which annotates each operation with
`x-permission-roles` (sourced from the `@require_role` decorator).

The output is a JSON mapping of endpoint paths and methods to the roles
that are permitted to call them.

Usage:

Activate the server virtualenv first (uv sync && source .venv/bin/activate)
or use the project uvx runner so imports and deps are available.

    # Generate the permissions to stdout
    python generate_permissions.py

    # Write the permissions to file
    python generate_permissions.py -o ../tests/permissions.json

    # Check if the committed file matches current API
    python generate_permissions.py -d ../tests/permissions.json
"""

import argparse
import json
import sys
from pathlib import Path

from generate_openapi_schema import generate_schema


def generate_permissions(spec: dict) -> dict:
    """Extract endpoint permissions from OpenAPI spec.

    :param spec: An OpenAPI specification dictionary.
    :returns: A dict mapping endpoint paths to HTTP methods to allowed roles.
    """
    permissions = {}

    for path, path_item in spec.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue

        path_permissions = {}
        for method in ("get", "post", "put", "patch", "delete"):
            operation = path_item.get(method)
            if not isinstance(operation, dict):
                continue

            roles = operation.get("x-permission-roles")
            if roles:
                # Store roles in the same order as in the spec
                path_permissions[method.upper()] = sorted(roles)

        if path_permissions:
            permissions[path] = path_permissions

    # Sort by path for consistent output
    return dict(sorted(permissions.items()))


def normalize_json(data: dict) -> str:
    """Normalize JSON to compact form for comparison."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def diff_permissions(local_path: Path) -> bool:
    """
    Generate permissions from code and compare with the local file.

    :param local_path: Path to the expected permissions file.
    :returns: True if files match, False otherwise.
    """
    generated = generate_permissions(generate_schema())

    if not local_path.exists():
        print(
            f"Error: Expected permissions file not found: {local_path}",
            file=sys.stderr,
        )
        return False

    with local_path.open() as f:
        local = json.load(f)

    # Compare using compact normalized form
    generated_normalized = normalize_json(generated)
    local_normalized = normalize_json(local)

    if generated_normalized != local_normalized:
        print("Error: permissions.json is out of date", file=sys.stderr)
        print("", file=sys.stderr)
        print(
            "To update permissions.json, run from server/ directory:",
            file=sys.stderr,
        )
        print(
            "  python scripts/generate_permissions.py "
            "-o tests/permissions.json",
            file=sys.stderr,
        )
        return False

    return True


def main():
    """Generate or validate the permissions matrix."""
    parser = argparse.ArgumentParser(
        description=(
            "Generate or validate the permissions matrix "
            "for Testflinger API endpoints"
        )
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Write permissions to specified file (default is stdout)",
    )
    parser.add_argument(
        "--diff",
        "-d",
        type=Path,
        help=(
            "Compare generated permissions with the specified file "
            "for validation"
        ),
    )

    args = parser.parse_args()

    if args.diff:
        if not diff_permissions(args.diff):
            sys.exit(1)
        print(" permissions.json is up to date")
        sys.exit(0)

    # Generation mode
    permissions = generate_permissions(generate_schema())

    if args.output:
        # Write to file with indentation for readability
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w") as f:
            json.dump(permissions, f, indent=2, sort_keys=True)
            f.write("\n")  # trailing linebreak
        print(f" Permissions written to: {args.output}")
    else:
        print(json.dumps(permissions, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
