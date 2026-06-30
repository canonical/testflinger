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
Generate the human-readable API.md from the OpenAPI schema.

The OpenAPI schema (schemas/openapi.json) is the single source of truth for
the API documentation. It is generated from the Flask application code (see
scripts/generate_openapi_schema.py): endpoint descriptions come from view
function docstrings, request/response details come from the marshmallow
schemas, and the following custom extensions enrich the generated markdown:

    x-codeSamples   List of {lang, label, source} curl/code examples that are
                    rendered under an "Examples:" section.
    x-notes         List of note/warning strings rendered as GitHub-style
                    "[!NOTE]" blockquotes.
    x-permission-roles  List of roles allowed to call the endpoint (added by
                    generate_openapi_schema.py from the @require_role
                    decorators), rendered under a "Required roles:" section.

Usage:

    # Write API.md from the committed schema
    python generate_api_md.py -s ../schemas/openapi.json -o ../API.md

    # Print to stdout
    python generate_api_md.py --schema ../schemas/openapi.json

    # Check the committed API.md matches what would be generated
    python generate_api_md.py --schema ../schemas/openapi.json --diff ../API.md
"""

import argparse
import json
import sys
from http import HTTPStatus
from pathlib import Path

# Render HTTP methods in this order when a path supports several of them.
METHOD_ORDER = ("post", "get", "put", "patch", "delete")

# Only document endpoints under this prefix (the public v1 REST API).
DOCUMENTED_PREFIX = "/v1/"

# Response descriptions that carry no extra information beyond the status code.
GENERIC_RESPONSE_DESCRIPTIONS = {"", "ok", "successful response"}


def resolve_ref(spec: dict, node: dict) -> dict:
    """Resolve a (possibly nested) ``$ref`` against the full spec.

    Only the leading ``$ref`` is resolved; the returned dict is the referenced
    component. Non-ref nodes are returned unchanged.
    """
    if not isinstance(node, dict):
        return node
    ref = node.get("$ref")
    if not ref:
        return node
    # e.g. "#/components/schemas/Job"
    parts = ref.lstrip("#/").split("/")
    target = spec
    for part in parts:
        target = target[part]
    return target


def schema_type_label(spec: dict, schema: dict) -> str:
    """Return a short human-readable type label for a schema node."""
    if not isinstance(schema, dict):
        return "object"
    if "$ref" in schema:
        return schema["$ref"].split("/")[-1]
    schema_type = schema.get("type")
    if schema_type == "array":
        item_label = schema_type_label(spec, schema.get("items", {}))
        return f"array of {item_label}"
    if schema_type:
        return schema_type
    # objects with additionalProperties (free-form mappings)
    if "additionalProperties" in schema:
        return "object"
    return "object"


def status_phrase(code: int) -> str:
    """Return the canonical reason phrase for an HTTP status code."""
    try:
        return HTTPStatus(code).phrase
    except ValueError:
        return ""


def render_parameters(spec: dict, operation: dict) -> list[str]:
    """Render the ``Parameters:`` section (path + query parameters)."""
    parameters = operation.get("parameters", [])
    if not parameters:
        return []

    lines = ["Parameters:", ""]
    for param in parameters:
        name = param.get("name", "")
        location = param.get("in", "")
        required = param.get("required", False)
        description = param.get("description", "")
        type_label = schema_type_label(spec, param.get("schema", {}))

        qualifiers = [type_label, location]
        if not required:
            qualifiers.append("optional")
        suffix = f": {description}" if description else ""
        lines.append(f"- `{name}` ({', '.join(qualifiers)}){suffix}")
    lines.append("")
    return lines


def render_headers(operation: dict) -> list[str]:
    """Render the ``Headers:`` section from the x-headers extension."""
    headers = operation.get("x-headers")
    if not headers:
        return []
    lines = ["Headers:", ""]
    for header in headers:
        lines.append(f"- {header}")
    lines.append("")
    return lines


def render_request_body(spec: dict, operation: dict) -> list[str]:
    """Render the ``Request Body:`` section from the request schema."""
    request_body = operation.get("requestBody")
    if not request_body:
        return []
    content = request_body.get("content", {}).get("application/json")
    if not content:
        return []

    schema = resolve_ref(spec, content.get("schema", {}))
    properties = schema.get("properties", {})
    if not properties:
        return []

    required_fields = set(schema.get("required", []))
    lines = ["Request Body:", ""]
    for field_name, field_schema in sorted(properties.items()):
        type_label = schema_type_label(spec, field_schema)
        description = field_schema.get("description", "")
        qualifiers = [type_label]
        if field_name not in required_fields:
            qualifiers.append("optional")
        suffix = f": {description}" if description else ""
        lines.append(f"- `{field_name}` ({', '.join(qualifiers)}){suffix}")
    lines.append("")
    return lines


def primary_success_response(operation: dict) -> tuple[str, dict] | None:
    """Return the (code, response) pair for the primary 2xx response."""
    responses = operation.get("responses", {})
    for code in sorted(responses):
        if str(code).startswith("2"):
            return code, responses[code]
    return None


def render_returns(spec: dict, operation: dict) -> list[str]:
    """Render the ``Returns:`` section from the primary success response."""
    success = primary_success_response(operation)
    if not success:
        return []
    _code, response = success

    content = response.get("content", {}).get("application/json")
    if not content:
        return []
    schema = content.get("schema", {})
    resolved = resolve_ref(spec, schema)

    # Skip empty/placeholder schemas ({}), which carry no useful information
    # (APIFlask emits these for endpoints declared without an output schema).
    informative_keys = {
        "type",
        "$ref",
        "properties",
        "items",
        "additionalProperties",
        "example",
    }
    if not (informative_keys & set(schema)) and not (
        informative_keys & set(resolved)
    ):
        return []

    # Prefer an explicit example if present on the schema.
    example = schema.get("example")
    if example is None:
        example = resolved.get("example")
    # Otherwise, synthesize one from per-property examples, if any.
    if example is None:
        properties = resolved.get("properties", {})
        synthesized = {
            name: prop["example"]
            for name, prop in properties.items()
            if isinstance(prop, dict) and "example" in prop
        }
        if synthesized:
            example = synthesized

    lines = ["Returns:", ""]
    if example is not None:
        lines.append("```json")
        lines.append(json.dumps(example, indent=2))
        lines.append("```")
        lines.append("")
        return lines

    type_label = schema_type_label(spec, schema)
    lines.append(f"JSON data matching the `{type_label}` schema.")
    lines.append("")
    return lines


def render_status_codes(operation: dict) -> list[str]:
    """Render the ``Status Codes:`` section from the responses object."""
    responses = operation.get("responses", {})
    if not responses:
        return []

    lines = ["Status Codes:", ""]
    for code in sorted(responses, key=int):
        response = responses[code]
        phrase = status_phrase(int(code))
        description = (response.get("description") or "").strip()
        # Skip descriptions that just restate the status code.
        if description.lower() in GENERIC_RESPONSE_DESCRIPTIONS or (
            description.lower() == phrase.lower()
        ):
            lines.append(f"- `HTTP {code} ({phrase})`")
        else:
            lines.append(f"- `HTTP {code} ({phrase})`: {description}")
    lines.append("")
    return lines


def render_roles(operation: dict) -> list[str]:
    """Render the ``Required roles:`` section from x-permission-roles."""
    roles = operation.get("x-permission-roles")
    if not roles:
        return []
    role_list = ", ".join(f"`{role}`" for role in roles)
    return [f"Required roles: {role_list}", ""]


def render_notes(operation: dict) -> list[str]:
    """Render ``x-notes`` as GitHub-style NOTE blockquotes."""
    notes = operation.get("x-notes")
    if not notes:
        return []
    lines = []
    for note in notes:
        lines.append("> [!NOTE]")
        for note_line in note.splitlines() or [""]:
            lines.append(f"> {note_line}".rstrip())
        lines.append("")
    return lines


def render_examples(operation: dict) -> list[str]:
    """Render the ``Examples:`` section from x-codeSamples."""
    samples = operation.get("x-codeSamples")
    if not samples:
        return []

    heading = "Examples:" if len(samples) > 1 else "Example:"
    lines = [heading, ""]
    for sample in samples:
        lang = sample.get("lang", "shell")
        label = sample.get("label", "")
        source = sample.get("source", "")
        # Show a descriptive label (anything other than the default "curl").
        if label and label.lower() != "curl":
            lines.append(f"{label}:")
            lines.append("")
        lines.append(f"```{lang}")
        lines.append(source)
        lines.append("```")
        lines.append("")
    return lines


def render_operation(
    spec: dict, path: str, method: str, operation: dict
) -> str:
    """Render a single endpoint operation as a markdown section."""
    # Convert OpenAPI path syntax back to the doc style: {var} -> <var>
    path_label = display_path(path)
    lines = [f"## `[{method.upper()}] {path_label}`", ""]

    summary = (operation.get("summary") or "").strip()
    description = (operation.get("description") or "").strip()
    if summary:
        lines.append(summary)
        lines.append("")
    if description:
        lines.append(description)
        lines.append("")

    lines += render_headers(operation)
    lines += render_parameters(spec, operation)
    lines += render_request_body(spec, operation)
    lines += render_returns(spec, operation)
    lines += render_status_codes(operation)
    lines += render_roles(operation)
    lines += render_notes(operation)
    lines += render_examples(operation)

    # Collapse any trailing blank lines for this section.
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def display_path(path: str) -> str:
    """Convert OpenAPI path syntax to the doc style: {var} -> <var>."""
    return path.replace("{", "<").replace("}", ">")


def order_key(method: str, path: str):
    """Sort key ordering operations alphabetically by path, then by method."""
    method_rank = (
        METHOD_ORDER.index(method)
        if method in METHOD_ORDER
        else len(METHOD_ORDER)
    )
    return (path, method_rank)


def generate_markdown(spec: dict) -> str:
    """Generate the full API.md content from an OpenAPI spec."""
    title = spec.get("info", {}).get("title", "API")
    sections = [f"# {title}", ""]

    paths = spec.get("paths", {})
    operations = []
    for path, path_item in paths.items():
        if not path.startswith(DOCUMENTED_PREFIX):
            continue
        if not isinstance(path_item, dict):
            continue
        for method in METHOD_ORDER:
            operation = path_item.get(method)
            if isinstance(operation, dict):
                operations.append((path, method, operation))

    operations.sort(key=lambda item: order_key(item[1], item[0]))

    rendered = [
        render_operation(spec, path, method, operation)
        for path, method, operation in operations
    ]

    sections.append("\n\n".join(rendered))
    return "\n".join(sections).rstrip() + "\n"


def main():
    """Parse arguments and generate, write, or diff the API.md content."""
    parser = argparse.ArgumentParser(
        description="Generate API.md from the OpenAPI schema"
    )
    parser.add_argument(
        "--schema",
        "-s",
        type=Path,
        default=Path(__file__).parent.parent / "schemas" / "openapi.json",
        help="Path to the OpenAPI schema JSON file",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Write markdown to specified file (default is stdout)",
    )
    parser.add_argument(
        "--diff",
        "-d",
        type=Path,
        help="Compare generated markdown with the specified file",
    )

    args = parser.parse_args()

    if not args.schema.exists():
        print(f"Error: schema file not found: {args.schema}", file=sys.stderr)
        sys.exit(1)

    with args.schema.open() as f:
        spec = json.load(f)

    markdown = generate_markdown(spec)

    if args.diff:
        if not args.diff.exists():
            print(
                f"Error: file to diff not found: {args.diff}", file=sys.stderr
            )
            sys.exit(1)
        existing = args.diff.read_text()
        if existing != markdown:
            print("Error: API.md is out of date", file=sys.stderr)
            print(
                "Regenerate it with: python scripts/generate_api_md.py "
                "--output API.md",
                file=sys.stderr,
            )
            sys.exit(1)
        print("API.md is up to date")
        sys.exit(0)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(markdown)
        print(f"API.md written to: {args.output}")
    else:
        sys.stdout.write(markdown)


if __name__ == "__main__":
    main()
