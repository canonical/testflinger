# Copyright (C) 2024 Canonical
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

"""Natural language queue/agent search via pydantic-ai and MCP servers.

Usage
-----
    testflinger find "Pi4 with Ubuntu Noble and serial console"
    testflinger find "x86 machine in London" --submit job.yaml --poll

If the testflinger-cli config file contains MCP server settings, they are
automatically used to resolve the natural language query against the hardware
inventory (e.g., C3/HEXR database), filtered to machines that have
``in_testflinger=true``. The resulting candidate machines are then
cross-referenced against the live Testflinger agent/queue list to produce
actionable queue names.

MCP server configuration lives in the testflinger-cli config file, e.g.:

    mcp.transport = stdio
    mcp.command = hexr-mcp

If MCP is not configured, the search falls back to fuzzy matching against
the live Testflinger queue list without hardware inventory knowledge.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from testflinger_cli.config import TestflingerCliConfig

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "anthropic/claude-haiku-4.5"


# ---------------------------------------------------------------------------
# API key configuration
# ---------------------------------------------------------------------------


def resolve_model(
    model: str | None, config: TestflingerCliConfig | None = None
) -> str:
    """Select the explicit model, configured default, or built-in default."""
    return (
        model
        or (config.get("model.default") if config is not None else None)
        or DEFAULT_MODEL
    )


def _normalize_model_string(model: str) -> str:
    """Normalize model string to include provider prefix if needed.

    Converts:
    - "anthropic/claude-haiku-4.5" -> "openrouter:anthropic/claude-haiku-4.5"
    - "openai/gpt-4o" -> "openrouter:openai/gpt-4o"
    - "openrouter:anthropic/claude-haiku-4.5" -> same (unchanged)
    - "anthropic:claude-3-5-haiku-20241022" -> same (unchanged)

    Parameters
    ----------
    model : str
        The model string, potentially in short OpenRouter format.

    Returns
    -------
    str
        The normalized model string suitable for pydantic-ai.
    """
    # If it already has a provider prefix, return it as-is.
    if ":" in model:
        return model

    # If it has a slash, assume it's short OpenRouter format and add the prefix
    if "/" in model:
        return f"openrouter:{model}"

    # Otherwise return as-is (might be a single model name that needs context)
    return model


def _copilot_auth_guidance(reason: str | None = None) -> str:
    """Explain how to sign in to GitHub Copilot using GitHub CLI."""
    details = (
        f"GitHub Copilot authentication failed: {reason}\n\n" if reason else ""
    )
    return (
        f"{details}Sign in with GitHub CLI, then retry; Testflinger reads the "
        "token automatically:\n"
        "  gh auth login --hostname github.com\n"
        "  uv run testflinger-cli find 'raspberry pi 4 with control_host_iot' "
        "--model github-copilot:claude-haiku-4.5\n\n"
        "Alternatively set model.github-copilot.api_key in your Testflinger "
        "config or export GITHUB_COPILOT_API_KEY. Your account must have "
        "Copilot access."
    )


def _setup_api_key_env(model: str, config: TestflingerCliConfig) -> None:
    """Set up environment variables for pydantic-ai based on the model string.

    Supports both full format (e.g., "openrouter:anthropic/claude-haiku-4.5")
    and short format (e.g., "anthropic/claude-haiku-4.5" for OpenRouter).

    pydantic-ai reads API keys from environment variables:
    - OPENROUTER_API_KEY for openrouter:* models or provider/model format
    - GITHUB_COPILOT_API_KEY for github-copilot:* models
    - OPENAI_API_KEY for openai:* models
    - ANTHROPIC_API_KEY for anthropic:* models
    - OLLAMA_API_KEY for ollama:* models (optional)

    This function extracts the config value for the API key (if present) and
    exports it to the environment so pydantic-ai can find it.

    Parameters
    ----------
    model : str
        The model string, e.g. "openrouter:anthropic/claude-haiku-4.5" or
        "anthropic/claude-haiku-4.5" (short OpenRouter format).
    config : TestflingerCliConfig
        The config object to read API keys from.
    """
    if model.startswith("openai:"):
        api_key = config.get("model.openai.api_key")
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
    elif model.startswith("openrouter:"):
        api_key = config.get("model.openrouter.api_key")
        if api_key:
            os.environ["OPENROUTER_API_KEY"] = api_key
    elif model.startswith("github-copilot:"):
        # Explicit environment/config credentials take precedence over gh.
        if not os.environ.get("GITHUB_COPILOT_API_KEY"):
            api_key = config.get("model.github-copilot.api_key")
            if api_key:
                os.environ["GITHUB_COPILOT_API_KEY"] = api_key
            else:
                try:
                    gh_path = shutil.which("gh")
                    if gh_path is None:
                        raise FileNotFoundError(
                            "GitHub CLI (`gh`) was not found."
                        )
                    result = subprocess.run(  # noqa: S603
                        [
                            gh_path,
                            "auth",
                            "token",
                            "--hostname",
                            "github.com",
                        ],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                except FileNotFoundError as exc:
                    raise ValueError(
                        _copilot_auth_guidance(
                            "GitHub CLI (`gh`) was not found."
                        )
                    ) from exc
                except subprocess.CalledProcessError as exc:
                    reason = exc.stderr.strip() or "No GitHub CLI login found."
                    raise ValueError(_copilot_auth_guidance(reason)) from exc

                token = result.stdout.strip()
                if not token:
                    raise ValueError(
                        _copilot_auth_guidance(
                            "`gh auth token` returned no token."
                        )
                    )
                os.environ["GITHUB_COPILOT_API_KEY"] = token
    elif model.startswith("anthropic:"):
        api_key = config.get("model.anthropic.api_key")
        if api_key:
            os.environ["ANTHROPIC_API_KEY"] = api_key
    elif model.startswith("ollama:"):
        api_key = config.get("model.ollama.api_key")
        if api_key:
            os.environ["OLLAMA_API_KEY"] = api_key
    elif "/" in model and not model.startswith("http"):
        # Assume it's a short OpenRouter format: "provider/model-name"
        # (e.g., "anthropic/claude-haiku-4.5")
        api_key = config.get("model.openrouter.api_key")
        if api_key:
            os.environ["OPENROUTER_API_KEY"] = api_key


def show_available_models(
    config: TestflingerCliConfig | None = None,
    model: str | None = None,
) -> None:
    """Show useful OpenRouter model IDs and the key's list if possible."""
    if model and model.startswith("github-copilot:"):
        _show_copilot_models(config)
        return

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key and config is not None:
        api_key = config.get("model.openrouter.api_key")

    if not api_key:
        print("Useful OpenRouter model IDs:")
        _print_relevant_model_examples()
        print(
            "\nSet OPENROUTER_API_KEY or model.openrouter.api_key in your "
            "Testflinger CLI config to also list models filtered by your "
            "OpenRouter account."
        )
        return

    try:
        _show_models_from_api(api_key)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Could not fetch OpenRouter models: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def _show_models_from_api(api_key: str) -> None:
    """Fetch and display models allowed by OpenRouter user preferences."""
    import json

    try:
        import urllib.error
        import urllib.request
    except ImportError:
        raise ImportError(
            "urllib is required to fetch OpenRouter models"
        ) from None

    url = "https://openrouter.ai/api/v1/models/user"
    headers = {
        "Authorization": f"Bearer {api_key}",
    }

    models = []
    next_url = url
    try:
        while next_url:
            req = urllib.request.Request(  # noqa: S310
                next_url, headers=headers
            )
            # URLs are constrained to the OpenRouter HTTPS origin above.
            with urllib.request.urlopen(req, timeout=10) as response:  # noqa: S310
                data = json.loads(response.read().decode())
            models.extend(data.get("data", []))
            next_url = data.get("links", {}).get("next")
            if next_url and next_url.startswith("/"):
                next_url = f"https://openrouter.ai{next_url}"
            if next_url and not next_url.startswith("https://openrouter.ai/"):
                raise ValueError(
                    "OpenRouter returned an unexpected pagination URL"
                )
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        TimeoutError,
    ) as exc:
        raise RuntimeError(
            f"OpenRouter model-list request failed: {exc}"
        ) from exc

    if not models:
        print("OpenRouter returned no models for this key's preferences/")
        print("guardrails.")
        return

    model_ids = sorted({model["id"] for model in models if model.get("id")})
    print(
        "OpenRouter models allowed by this key's preferences and guardrails:"
    )
    for model_id in model_ids:
        print(f"  {model_id}")
    print(f"\n{len(model_ids)} models returned by /models/user.")
    print(
        "This list reflects OpenRouter's account filters; model availability "
        "can still change before an inference request."
    )
    print("\nUseful model IDs to try:")
    _print_relevant_model_examples()


def _print_relevant_model_examples() -> None:
    """Print current, task-relevant model IDs in OpenRouter format."""
    print("  anthropic/claude-haiku-4.5")
    print("  openai/gpt-4o-mini")
    print("\nExample:")
    print(
        "  uv run testflinger-cli find "
        "'raspberry pi 4 with control_host_iot' "
        "--model openai/gpt-4o-mini"
    )


def _show_copilot_models(config: TestflingerCliConfig | None) -> None:
    """List Copilot models available to the authenticated GitHub account."""
    if config is None:
        from testflinger_cli.config import (
            TestflingerCliConfig as Config,  # noqa: PLC0415
        )

        config = Config()

    try:
        _setup_api_key_env("github-copilot:claude-haiku-4.5", config)
        _fetch_copilot_models(os.environ["GITHUB_COPILOT_API_KEY"])
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Could not fetch GitHub Copilot models: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def _fetch_copilot_models(api_key: str) -> None:
    """Fetch and display Copilot models reachable through Chat Completions."""
    import json
    import urllib.error
    import urllib.request

    request = urllib.request.Request(
        "https://api.githubcopilot.com/models",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Copilot-Integration-Id": os.environ.get(
                "GITHUB_COPILOT_INTEGRATION_ID", "vscode-chat"
            ),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
            payload = json.loads(response.read().decode())
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        TimeoutError,
    ) as exc:
        raise RuntimeError(
            f"Copilot model-list request failed: {exc}"
        ) from exc

    models = payload.get("data", [])
    chat_models = [
        model
        for model in models
        if "/chat/completions" in model.get("supported_endpoints", [])
    ]
    print("GitHub Copilot models available through Pydantic AI:")
    if not chat_models:
        print("  No Chat Completions models were returned for this account.")
    for model in sorted(chat_models, key=lambda item: item.get("id", "")):
        print(f"  github-copilot:{model['id']}")
    print(
        "\nPydantic AI uses Copilot's Chat Completions API; model access "
        "depends on your Copilot plan."
    )


# ---------------------------------------------------------------------------
# MCP server configuration helpers
# ---------------------------------------------------------------------------


@dataclass
class MCPServerConfig:
    """Resolved configuration for a named MCP server."""

    label: str
    transport: str  # "stdio" | "sse"
    command: str | None = (
        None  # stdio only: executable (+ args split by space)
    )
    url: str | None = None  # sse only
    env: dict[str, str] | None = None  # stdio environment variables


def load_mcp_config(config: "TestflingerCliConfig") -> MCPServerConfig | None:
    """Load MCP server config from the CLI config file.

    Config keys are read from the flat configparser namespace, e.g.:

        mcp.transport = stdio
        mcp.command = hexr-mcp --flag
        mcp.env.HEXR_TOKEN = ${HEXR_TOKEN}

    Returns
    -------
    MCPServerConfig | None
        The resolved MCP server config, or None if MCP is not configured.

    Raises
    ------
    ValueError
        If required keys are missing or transport is invalid.
    """
    prefix = "mcp."
    transport = config.get(f"{prefix}transport")
    if transport is None:
        # MCP is not configured
        return None

    transport = transport.strip().lower()

    if transport == "stdio":
        command = config.get(f"{prefix}command")
        if not command:
            raise ValueError(
                f"MCP server uses stdio transport but '{prefix}command' is "
                "not set."
            )
        env_prefix = f"{prefix}env."
        env = {
            key[len(env_prefix) :].upper(): os.path.expandvars(value)
            for key, value in config.data.items()
            if key.startswith(env_prefix) and len(key) > len(env_prefix)
        }
        return MCPServerConfig(
            label="mcp",
            transport="stdio",
            command=command,
            env=env or None,
        )

    if transport == "sse":
        url = config.get(f"{prefix}url")
        if not url:
            raise ValueError(
                f"MCP server uses sse transport but '{prefix}url' is not set."
            )
        return MCPServerConfig(label="mcp", transport="sse", url=url)

    raise ValueError(
        f"Unknown MCP transport '{transport}'. Expected 'stdio' or 'sse'."
    )


# ---------------------------------------------------------------------------
# Agent / queue resolution
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a Testflinger hardware-allocation assistant.

Your goal is to map a natural language description of required hardware to one
or more Testflinger queue names that the user can actually submit jobs to.

You have access to the hexr-mcp tool `hardware_list_hardware`.  Always filter
with `in_testflinger=true` so you only consider machines that are available in
the Testflinger lab.

Workflow:
1. Call `hardware_list_hardware` with `in_testflinger=true` and whatever
   filters best match the user's description (arch, cpu_model, category,
   gpu_name, memory_gte, provision_type, etc.).
2. From results collect `canonical_label` for the matching machines.
3. Call `match_hardware_to_live_agents` with those labels. This returns actual
   Testflinger agent names, provision types, queues, and online state.
4. Compare each agent's connector/provision type with the complete job
   requirements supplied in the user message. Do not select incompatible
   agents.
5. Return only queues belonging to compatible online agents, best match first,
   one per line.
6. If no compatible online agents or queues are found, return an empty
   response.
7. Do not claim the queue list is missing or request that the user provide it;
   the tool supplies the relevant live agent and queue data.
8. Do not add explanations, commentary, or punctuation — queue names only.
"""


def _tool_was_called(messages, tool_name: str) -> bool:
    """Check whether a named tool returned during this agent run."""
    from pydantic_ai.messages import (  # noqa: PLC0415
        ModelRequest,
        ToolReturnPart,
    )

    return any(
        part.tool_name == tool_name
        for message in messages
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, ToolReturnPart)
    )


def _inventory_tool_was_called(messages) -> bool:
    """Check whether the HEXR inventory tool returned during this run."""
    return _tool_was_called(messages, "hardware_list_hardware")


def _tool_was_requested(messages, tool_name: str) -> bool:
    """Check whether a named tool call was issued during the agent run."""
    from pydantic_ai.messages import (  # noqa: PLC0415
        ModelResponse,
        ToolCallPart,
    )

    return any(
        part.tool_name == tool_name
        for message in messages
        if isinstance(message, ModelResponse)
        for part in message.parts
        if isinstance(part, ToolCallPart)
    )


def _mcp_tools_include_inventory(tools: list[object]) -> bool:
    """Return whether the connected MCP server exposes hardware inventory."""
    return any(
        getattr(tool, "name", None) == "hardware_list_hardware"
        for tool in tools
    )


ONLINE_AGENT_STATES = frozenset(
    {
        "waiting",
        "setup",
        "provision",
        "firmware_update",
        "test",
        "allocate",
        "reserve",
        "cleanup",
    }
)


def queues_from_online_agents(agents: list[dict]) -> list[str]:
    """Return unique queues currently served by online Testflinger agents."""
    queues = dict.fromkeys(
        str(queue)
        for agent in agents
        if agent.get("state") in ONLINE_AGENT_STATES
        for queue in agent.get("queues", [])
        if queue
    )
    return list(queues)


def match_agents_to_canonical_labels(
    agents: list[dict], canonical_labels: list[str]
) -> list[dict[str, object]]:
    """Return agent records for C3 labels, including online state."""
    normalized_labels = [
        _normalize_agent_name(label)
        for label in canonical_labels
        if label and _normalize_agent_name(label)
    ]
    matches: list[dict[str, object]] = []
    for agent in agents:
        name = str(agent.get("name", ""))
        normalized_name = _normalize_agent_name(name)
        if not normalized_name or not any(
            label in normalized_name or normalized_name in label
            for label in normalized_labels
        ):
            continue
        state = str(agent.get("state", "unknown"))
        matches.append(
            {
                "name": name,
                "state": state,
                "online": state in ONLINE_AGENT_STATES,
                "queues": [
                    str(queue) for queue in agent.get("queues", []) if queue
                ],
            }
        )
    return matches


def _normalize_agent_name(value: str) -> str:
    """Normalize labels and agent names for punctuation-insensitive matches."""
    return "".join(
        character.casefold() for character in value if character.isalnum()
    )


def _job_matching_context(job_data: dict | None) -> dict[str, object] | None:
    """Return job requirements without secrets or executable scripts."""
    if not job_data:
        return None

    excluded_keys = {
        "password",
        "secret",
        "secrets",
        "token",
        "authorization",
        "credentials",
        "ssh_keys",
        "test_cmds",
        "user_data",
        "autoinstall_base_user_data",
    }

    def sanitize(value):
        if isinstance(value, dict):
            return {
                key: sanitize(item)
                for key, item in value.items()
                if not any(term in key.casefold() for term in excluded_keys)
            }
        if isinstance(value, list):
            return [sanitize(item) for item in value]
        return value

    return sanitize(
        {
            key: value
            for key, value in job_data.items()
            if key not in {"job_queue", "job_id"}
        }
    )


def filter_ranked_queues(
    model_output: str, allowed_queues: list[str]
) -> list[str]:
    """Keep only unique queue names actually offered by matched agents."""
    allowed = set(allowed_queues)
    results = []
    for line in model_output.splitlines():
        candidate = line.strip().strip("`*•- ").strip()
        if candidate in allowed and candidate not in results:
            results.append(candidate)
    return results


def _redact_mcp_secrets(message: str, env: dict[str, str] | None) -> str:
    """Redact configured MCP environment values from diagnostic text."""
    for secret in (env or {}).values():
        if secret:
            message = message.replace(secret, "[redacted]")
    return message


async def _find_with_mcp(
    query: str,
    mcp_cfg: MCPServerConfig,
    model: str,
    live_agents: list[dict],
    job_data: dict | None = None,
) -> list[str]:
    """Run the NL search against the hexr-mcp server using pydantic-ai.

    Parameters
    ----------
    query:
        Natural language hardware description from the user.
    mcp_cfg:
        Resolved hexr-mcp server config (stdio or sse).
    model:
        pydantic-ai model string.
    live_agents:
        Agent records from Testflinger's /v1/agents/data endpoint. The local
        matching tool only returns online agents whose names match C3 labels.
    job_data:
        Optional complete job definition, sanitized before model context.
    """
    try:
        from pydantic_ai import Agent  # noqa: PLC0415
        from pydantic_ai.capabilities import (
            AbstractCapability,  # noqa: PLC0415
        )
        from pydantic_ai.mcp import (  # noqa: PLC0415
            FastMCPClient,
            MCPToolset,
            SSETransport,
            StdioTransport,
        )
        from pydantic_ai.settings import ModelSettings  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "pydantic-ai is required for MCP-backed search. "
            "Install it with: pip install testflinger-cli"
        ) from exc

    if mcp_cfg.transport == "stdio":
        parts = shlex.split(mcp_cfg.command or "")
        if not parts:
            raise ValueError("MCP stdio command is empty.")
        transport = StdioTransport(
            parts[0],
            args=parts[1:],
            env=mcp_cfg.env,
        )
    else:
        transport = SSETransport(mcp_cfg.url)  # type: ignore[arg-type]

    client = FastMCPClient(transport, mode="legacy")
    toolset = MCPToolset(
        client,
        include_instructions=True,
        tool_error_behavior="error",
    )

    try:
        mcp_tools = await toolset.list_tools()
    except Exception as exc:
        message = _redact_mcp_secrets(str(exc), mcp_cfg.env)
        raise RuntimeError(
            f"Could not connect to MCP server '{mcp_cfg.label}' or list its "
            f"tools: {message}"
        ) from exc

    tool_names = [getattr(tool, "name", "<unnamed>") for tool in mcp_tools]
    if not _mcp_tools_include_inventory(mcp_tools):
        raise RuntimeError(
            f"MCP server '{mcp_cfg.label}' connected, but does not expose "
            "the required 'hardware_list_hardware' tool. Tools returned: "
            f"{', '.join(tool_names) or '(none)'}. Verify this is the HEXR/C3 "
            "MCP server and check its own authentication setup."
        )
    logger.info(
        "Connected to MCP server '%s'; hardware_list_hardware is available.",
        mcp_cfg.label,
    )

    @dataclass
    class RequireInventoryAndAgentMatch(AbstractCapability[None]):
        """Require both lookup tools before the agent may answer."""

        def get_model_settings(self):
            def settings(ctx):
                if not _inventory_tool_was_called(ctx.messages):
                    return ModelSettings(
                        tool_choice=["hardware_list_hardware"]
                    )
                if not _tool_was_called(
                    ctx.messages, "match_hardware_to_live_agents"
                ):
                    return ModelSettings(
                        tool_choice=["match_hardware_to_live_agents"]
                    )
                return ModelSettings()

            return settings

    job_context = _job_matching_context(job_data)
    matched_agent_records: list[dict[str, object]] = []

    def match_hardware_to_live_agents(
        canonical_labels: list[str],
        required_provision_type: str | None = None,
    ) -> list[dict[str, object]]:
        """Match C3 labels to online agents and return their metadata."""
        matches = match_agents_to_canonical_labels(
            live_agents, canonical_labels
        )
        matched_agent_records[:] = matches
        return matches

    agent: Agent[None, str] = Agent(
        model,
        tools=[match_hardware_to_live_agents],
        toolsets=[toolset],
        system_prompt=SYSTEM_PROMPT,
        capabilities=[RequireInventoryAndAgentMatch()],
    )

    user_message = (
        f"Hardware description: {query}\n\n"
        "Job definition (do not change its requested test/provisioning "
        f"requirements): {job_context or '(not supplied)'}\n\n"
        "First call hardware_list_hardware with in_testflinger=true. Then "
        "pass its canonical_label values and the job's provision_type (if "
        "specified) to match_hardware_to_live_agents. Compare the returned "
        "agent provision_type, queues, and identity against the full job "
        "definition above. Select only an online agent whose provision type "
        "supports the job's provisioning/device-connector needs. Then return "
        "one of that agent's queues. Return "
        "queue names best match first, one per line. If there are no online "
        "matches, return an empty response. "
        "Do not ask the user for queue names or speculate about credentials; "
        "tool errors will be reported by the CLI."
    )

    try:
        result = await agent.run(user_message)
    except Exception as exc:
        message = _redact_mcp_secrets(str(exc), mcp_cfg.env)
        raise RuntimeError(
            f"MCP-backed hardware inventory search failed: {message}"
        ) from exc

    allowed_queues = [
        str(queue)
        for match in matched_agent_records
        if match.get("online") is True
        for queue in match.get("queues", [])
    ]
    lines = filter_ranked_queues(result.output, allowed_queues)
    if not _inventory_tool_was_called(result.all_messages()):
        raise RuntimeError(
            "The model did not call the required hardware inventory tool. "
            "No queue recommendation was produced. Check that the selected "
            "model supports tool calling, then retry with a tool-capable "
            "model."
        )
    if not _tool_was_requested(
        result.all_messages(), "match_hardware_to_live_agents"
    ):
        raise RuntimeError(
            "The model did not call match_hardware_to_live_agents after "
            "the inventory lookup. No live queue match was completed."
        )
    if not lines:
        raise RuntimeError(
            "The model did not return a queue from the matched online agents. "
            "No queue recommendation was produced."
        )
    return lines


def _normalize_agent_name(value: str) -> str:
    """Normalize labels and agent names for punctuation-insensitive matches."""
    return "".join(
        character.casefold() for character in value if character.isalnum()
    )


ONLINE_AGENT_STATES = frozenset(
    {
        "online",
        "waiting",
        "setup",
        "provision",
        "firmware_update",
        "test",
        "allocate",
        "reserve",
        "cleanup",
    }
)


async def _find_without_mcp(
    query: str,
    queues: list[str],
    model: str,
    job_data: dict | None = None,
) -> list[str]:
    """Run the NL search against a plain list of queue names (no MCP server).

    Used when --mcp is not specified.  Without hardware inventory knowledge
    the LLM can only do fuzzy name matching against the raw queue list.
    """
    try:
        from pydantic_ai import Agent  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "pydantic-ai is required for natural language search. "
            "Install it with: pip install testflinger-cli[nlsearch]"
        ) from exc

    fallback_prompt = """\
You are a Testflinger hardware-allocation assistant.

Given a list of Testflinger queue names and a hardware description, return
the queue names that best match the description, best match first, one per
line.  Only return names from the provided list.  If no confident match is
found, return an empty response.  No explanations or punctuation.
"""
    queue_list = "\n".join(f"  - {q}" for q in queues)
    agent: Agent[None, str] = Agent(model, system_prompt=fallback_prompt)
    result = await agent.run(
        f"Available queues:\n{queue_list}\n\n"
        f"Hardware description: {query}\n\n"
        "Job definition: "
        f"{_job_matching_context(job_data) or '(not supplied)'}"
    )
    lines = [
        line.strip() for line in result.output.splitlines() if line.strip()
    ]
    return lines


def find_queues(
    query: str,
    *,
    mcp_cfg: MCPServerConfig | None = None,
    live_queues: list[str] | None = None,
    live_agents: list[dict] | None = None,
    job_data: dict | None = None,
    model: str | None = None,
    config: TestflingerCliConfig | None = None,
) -> list[str]:
    """Resolve *query* to a list of queue names (synchronous entry point).

    Parameters
    ----------
    query:
        Natural language description of required hardware.
    mcp_cfg:
        Resolved hexr-mcp server config.  When provided the agent uses the
        hexr-mcp ``hardware_list_hardware`` tool (filtered to
        ``in_testflinger=true``) and cross-references results against
        matching Testflinger agents and their queues. Without MCP the search
        falls back to fuzzy matching against *live_queues*.
    live_queues:
        Curated advertised queue names; used only in non-MCP fallback mode.
    live_agents:
        Agent records including online state and queue memberships. Required
        for MCP-backed matching.
    model:
        Model string. Can use either format:
        - Full: ``"openrouter:anthropic/claude-haiku-4.5"``
        - Short: ``"anthropic/claude-haiku-4.5"``
    config:
        TestflingerCliConfig object used to resolve API keys.  If ``None``,
        API keys must already be in the environment.

    Returns
    -------
    list[str]
        Queue names ranked by relevance (best match first).
    """
    # Resolve the model before configuring credentials for its provider.
    model = _normalize_model_string(resolve_model(model, config))

    if config is not None:
        _setup_api_key_env(model, config)

    if mcp_cfg is not None:
        if live_agents is None:
            raise ValueError(
                "MCP-backed find requires live Testflinger agent data."
            )
        return asyncio.run(
            _find_with_mcp(query, mcp_cfg, model, live_agents, job_data)
        )
    return asyncio.run(
        _find_without_mcp(query, live_queues or [], model, job_data)
    )
