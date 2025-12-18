#!/usr/bin/env python3
# Copyright (C) 2025 Canonical
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
Generate or validate the OpenAPI schema for Testflinger server.

This script extracts the OpenAPI specification from the Flask application
without requiring MongoDB or OIDC services.

Usage:
    # Generate schema to stdout
    python generate_openapi_schema.py

    # Write schema to file
    python generate_openapi_schema.py --output ../schemas/openapi.json

    # Check if committed schema matches current API
    python generate_openapi_schema.py --diff ../schemas/openapi.json
"""

import argparse
import json
import sys
from pathlib import Path

# Add devel directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from devel.openapi_app import app


def generate_schema() -> dict:
    """Get OpenAPI schema from Flask application in testing mode"""
    with app.app_context():
        return app.spec


def normalize_json(data: dict) -> str:
    """Normalize JSON to compact form for comparison"""
    return json.dumps(data, sort_keys=True, separators=(',', ':'))


def diff_schemas(local_schema_path: Path) -> bool:
    """
    Generate API schema from code and compare with the local schema file.
    Compare using compact JSON form for accuracy.

    Args:
        expected_path: Path to the expected schema file

    Returns:
        True if schemas match, False otherwise
    """
    generated = generate_schema()

    if not local_schema_path.exists():
        print(f"Error: Expected schema file not found: {local_schema_path}", file=sys.stderr)
        return False

    with local_schema_path.open() as f:
        local = json.load(f)

    # Compare using compact normalized form
    generated_normalized = normalize_json(generated)
    local_normalized = normalize_json(local)

    if generated_normalized != local_normalized:
        print("Error: OpenAPI schema is out of date", file=sys.stderr)
        print("", file=sys.stderr)
        print("To update the schema, run from server/ directory:", file=sys.stderr)
        print(f"  python scripts/generate_openapi_schema.py --output {local_schema_path}", file=sys.stderr)
        return False

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Generate or validate OpenAPI schema for Testflinger server"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("./openapi.json"),
        help="Write schema to specified file (default: ./openapi.json)"
    )
    parser.add_argument(
        "--diff",
        type=Path,
        help="Compare generated schema with the specified file for validation"
    )

    args = parser.parse_args()

    if args.diff:
        if not diff_schemas(args.diff):
            sys.exit(1)
        print(" OpenAPI schema is up to date")
        sys.exit(0)

    # Generation mode
    schema = generate_schema()

    if args.output:
        # Write to file with indentation for readability
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w") as f:
            json.dump(schema, f, indent=2, sort_keys=True)
            f.write("\n")       # trailing linebreak
        print(f" Schema written to: {args.output}")
    else:
        print(json.dumps(schema, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
