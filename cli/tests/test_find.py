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

"""Unit tests for the find module."""

import json
import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from testflinger_cli.config import TestflingerCliConfig
from testflinger_cli.find import (
    MCPServerConfig,
    _fetch_copilot_models,
    _mcp_tools_include_inventory,
    _normalize_model_string,
    _redact_mcp_secrets,
    _setup_api_key_env,
    _show_models_from_api,
    _tool_was_called,
    _tool_was_requested,
    find_queues,
    load_mcp_config,
    match_agents_to_canonical_labels,
    queues_from_online_agents,
    show_available_models,
)


def test_default_model_normalizes_to_openrouter_haiku_45():
    """The default model is Claude Haiku 4.5 on OpenRouter."""
    from testflinger_cli.find import find_queues

    assert (
        _normalize_model_string(find_queues.__kwdefaults__["model"])
        == "openrouter:anthropic/claude-haiku-4.5"
    )


def test_mcp_inventory_preflight_checks_required_tool():
    """Require the expected hardware inventory tool to be exposed."""
    assert _mcp_tools_include_inventory(
        [type("Tool", (), {"name": "hardware_list_hardware"})()]
    )
    assert not _mcp_tools_include_inventory(
        [type("Tool", (), {"name": "other_tool"})()]
    )
    assert not _mcp_tools_include_inventory([])


def test_mcp_diagnostics_redact_configured_env_values():
    """Never echo MCP credentials while reporting server errors."""
    assert (
        _redact_mcp_secrets(
            "Auth failed for secret-value", {"HEXR_TOKEN": "secret-value"}
        )
        == "Auth failed for [redacted]"
    )


def test_queues_from_online_agents_includes_unadvertised_agent_queues():
    """Agent membership provides queues without curated advertisements."""
    agents = [
        {
            "name": "pi4-agent-1",
            "state": "waiting",
            "queues": ["pi4-noble", "arm64"],
        },
        {
            "name": "pi4-agent-2",
            "state": "offline",
            "queues": ["pi4-offline"],
        },
        {"name": "x86-agent", "state": "test", "queues": ["x86"]},
    ]

    assert queues_from_online_agents(agents) == ["pi4-noble", "arm64", "x86"]


def test_match_agents_to_canonical_labels_returns_online_and_offline_state():
    """Match C3 canonical labels to agent identity and queue membership."""
    agents = [
        {
            "name": "agent-2026-pi4-lab",
            "state": "waiting",
            "queues": ["pi4-noble", "arm64"],
        },
        {
            "name": "agent-pi4-offline",
            "state": "offline",
            "queues": ["pi4-offline"],
        },
        {"name": "agent-x86", "state": "test", "queues": ["x86"]},
    ]
    matched = match_agents_to_canonical_labels(agents, ["pi4-lab"])

    assert matched == [
        {
            "name": "agent-2026-pi4-lab",
            "state": "waiting",
            "online": True,
            "queues": ["pi4-noble", "arm64"],
        }
    ]


def test_inventory_and_agent_match_tool_call_detection():
    """Treat both required calls as outstanding until each result returns."""
    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
        ToolCallPart,
        ToolReturnPart,
    )

    inventory_call = ModelResponse(
        parts=[ToolCallPart(tool_name="hardware_list_hardware", args={})]
    )
    inventory_result = ModelRequest(
        parts=[
            ToolReturnPart(tool_name="hardware_list_hardware", content="[]")
        ]
    )
    agent_call = ModelResponse(
        parts=[
            ToolCallPart(tool_name="match_hardware_to_live_agents", args={})
        ]
    )
    history = [inventory_call, inventory_result]

    assert _tool_was_requested(history, "hardware_list_hardware")
    assert _tool_was_called(history, "hardware_list_hardware")
    assert not _tool_was_called(history, "match_hardware_to_live_agents")

    history.append(agent_call)
    assert _tool_was_requested(history, "match_hardware_to_live_agents")


def test_require_lookups_forces_hardware_search_then_agent_match():
    """Ensure the required-tool guard recognizes inventory results."""
    from pydantic_ai.messages import ModelRequest, ToolReturnPart

    from testflinger_cli.find import _tool_was_called

    history = []
    history.append(
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="hardware_list_hardware", content="[]"
                )
            ]
        )
    )
    assert _tool_was_called(history, "hardware_list_hardware")
    assert not _tool_was_called(history, "match_hardware_to_live_agents")

    history.append(
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="match_hardware_to_live_agents", content="[]"
                )
            ]
        )
    )
    assert _tool_was_called(history, "match_hardware_to_live_agents")


def test_queues_from_online_agents_uses_membership_not_advertised_catalog():
    """Find queues from active agents even when they are unadvertised."""
    agents = [
        {
            "name": "pi4-agent-1",
            "state": "waiting",
            "queues": ["pi4", "arm64"],
        },
        {"name": "pi4-agent-2", "state": "offline", "queues": ["pi4-offline"]},
        {"name": "x86-agent", "state": "test", "queues": ["x86", "arm64"]},
    ]

    assert queues_from_online_agents(agents) == ["pi4", "arm64", "x86"]


def test_match_canonical_labels_to_online_testflinger_agents():
    """Associate C3 canonical labels with online agents and their queues."""
    agents = [
        {
            "name": "agent-2026-pi4-lab",
            "state": "waiting",
            "queues": ["pi4-noble", "arm64"],
        },
        {
            "name": "agent-pi4-offline",
            "state": "offline",
            "queues": ["pi4-offline"],
        },
        {"name": "agent-x86", "state": "test", "queues": ["x86"]},
    ]

    matches = match_agents_to_canonical_labels(agents, ["pi4-lab", "unknown"])

    assert matches == [
        {
            "name": "agent-2026-pi4-lab",
            "state": "waiting",
            "online": True,
            "queues": ["pi4-noble", "arm64"],
        }
    ]


def test_short_haiku_45_model_normalizes_to_openrouter():
    """Normalize Claude Haiku 4.5's OpenRouter model ID."""
    assert (
        _normalize_model_string("anthropic/claude-haiku-4.5")
        == "openrouter:anthropic/claude-haiku-4.5"
    )


def test_short_gpt_4o_mini_model_normalizes_to_openrouter():
    """Normalize GPT-4o mini's OpenRouter model ID."""
    assert (
        _normalize_model_string("openai/gpt-4o-mini")
        == "openrouter:openai/gpt-4o-mini"
    )


def test_show_models_uses_configured_openrouter_key(tmp_path, monkeypatch):
    """The model listing uses the API key stored in CLI config."""
    config_file = tmp_path / "test.conf"
    config_file.write_text(
        "[testflinger-cli]\nmodel.openrouter.api_key = sk-or-from-config\n"
    )
    config = TestflingerCliConfig(config_file)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    with patch("testflinger_cli.find._show_models_from_api") as show_from_api:
        show_available_models(config)

    show_from_api.assert_called_once_with("sk-or-from-config")


def test_show_models_without_key_shows_relevant_model_examples(
    monkeypatch, capsys
):
    """Show useful model IDs even when no API key is configured."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    show_available_models()

    output = capsys.readouterr().out
    assert "anthropic/claude-haiku-4.5" in output
    assert "openai/gpt-4o-mini" in output
    assert "--model openai/gpt-4o-mini" in output


def test_show_models_calls_openrouter_user_models_endpoint(
    monkeypatch, capsys
):
    """Display IDs from OpenRouter's account-filtered model endpoint."""
    response = MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps(
        {
            "data": [
                {"id": "anthropic/claude-haiku-4.5"},
                {"id": "openai/gpt-example"},
            ],
            "links": {"next": None},
        }
    ).encode()
    urlopen = MagicMock(return_value=response)
    monkeypatch.setattr("urllib.request.urlopen", urlopen)

    _show_models_from_api("sk-or-test")

    request = urlopen.call_args.args[0]
    assert request.full_url == "https://openrouter.ai/api/v1/models/user"
    assert request.get_header("Authorization") == "Bearer sk-or-test"
    output = capsys.readouterr().out
    assert "anthropic/claude-haiku-4.5" in output
    assert "2 models returned" in output


class TestMCPServerConfig:
    """Test MCPServerConfig dataclass."""

    def test_stdio_config(self):
        """Test creating a stdio transport config."""
        cfg = MCPServerConfig(
            label="hexr",
            transport="stdio",
            command="hexr-mcp --flag",
        )
        assert cfg.label == "hexr"
        assert cfg.transport == "stdio"
        assert cfg.command == "hexr-mcp --flag"
        assert cfg.url is None

    def test_sse_config(self):
        """Test creating an SSE transport config."""
        cfg = MCPServerConfig(
            label="mylab",
            transport="sse",
            url="https://lab.internal/mcp",
        )
        assert cfg.label == "mylab"
        assert cfg.transport == "sse"
        assert cfg.url == "https://lab.internal/mcp"
        assert cfg.command is None


class TestLoadMCPConfig:
    """Test load_mcp_config function."""

    def test_load_stdio_config(self, tmp_path):
        """Test loading a stdio transport MCP config."""
        config_file = tmp_path / "test.conf"
        config_file.write_text(
            "[testflinger-cli]\n"
            "mcp.transport = stdio\n"
            "mcp.command = hexr-mcp\n"
        )

        config = TestflingerCliConfig(config_file)
        mcp_cfg = load_mcp_config(config)

        assert mcp_cfg is not None
        assert mcp_cfg.label == "mcp"
        assert mcp_cfg.transport == "stdio"
        assert mcp_cfg.command == "hexr-mcp"
        assert mcp_cfg.url is None

    def test_load_stdio_config_and_forward_env(self, tmp_path, monkeypatch):
        """Load flat mcp settings and forward env to the stdio subprocess."""
        monkeypatch.setenv("HEX_TOKEN", "local-secret")
        config_file = tmp_path / "test.conf"
        config_file.write_text(
            "[testflinger-cli]\n"
            "mcp.transport = stdio\n"
            "mcp.command = hexr-mcp --verbose\n"
            "mcp.env.HEXR_TOKEN = ${HEX_TOKEN}\n"
        )
        config = TestflingerCliConfig(config_file)

        mcp_cfg = load_mcp_config(config)

        assert mcp_cfg is not None
        assert mcp_cfg.label == "mcp"
        assert mcp_cfg.command == "hexr-mcp --verbose"
        assert mcp_cfg.env == {"HEXR_TOKEN": "local-secret"}

    def test_load_sse_config(self, tmp_path):
        """Test loading an SSE transport MCP config."""
        config_file = tmp_path / "test.conf"
        config_file.write_text(
            "[testflinger-cli]\n"
            "mcp.transport = sse\n"
            "mcp.url = https://lab.internal/mcp\n"
        )

        config = TestflingerCliConfig(config_file)
        mcp_cfg = load_mcp_config(config)

        assert mcp_cfg is not None
        assert mcp_cfg.label == "mcp"
        assert mcp_cfg.transport == "sse"
        assert mcp_cfg.url == "https://lab.internal/mcp"
        assert mcp_cfg.command is None

    def test_mcp_not_configured(self, tmp_path):
        """Test when MCP is not configured (returns None)."""
        config_file = tmp_path / "test.conf"
        config_file.write_text("[testflinger-cli]\n")

        config = TestflingerCliConfig(config_file)
        mcp_cfg = load_mcp_config(config)

        assert mcp_cfg is None

    def test_missing_command_for_stdio(self, tmp_path):
        """Test error when stdio config missing command."""
        config_file = tmp_path / "test.conf"
        config_file.write_text("[testflinger-cli]\nmcp.transport = stdio\n")

        config = TestflingerCliConfig(config_file)
        with pytest.raises(ValueError, match="command.*not set"):
            load_mcp_config(config)

    def test_missing_url_for_sse(self, tmp_path):
        """Test error when SSE config missing URL."""
        config_file = tmp_path / "test.conf"
        config_file.write_text("[testflinger-cli]\nmcp.transport = sse\n")

        config = TestflingerCliConfig(config_file)
        with pytest.raises(ValueError, match="url.*not set"):
            load_mcp_config(config)

    def test_unknown_transport(self, tmp_path):
        """Test error for unknown transport type."""
        config_file = tmp_path / "test.conf"
        config_file.write_text("[testflinger-cli]\nmcp.transport = invalid\n")

        config = TestflingerCliConfig(config_file)
        with pytest.raises(ValueError, match="Unknown MCP transport"):
            load_mcp_config(config)


class TestSetupApiKeyEnv:
    """Test _setup_api_key_env function."""

    def test_openai_model_with_api_key(self, tmp_path):
        """Test setting OPENAI_API_KEY from config."""
        config_file = tmp_path / "test.conf"
        config_file.write_text(
            "[testflinger-cli]\nmodel.openai.api_key = sk-test123\n"
        )

        config = TestflingerCliConfig(config_file)

        # Clear any existing env var
        os.environ.pop("OPENAI_API_KEY", None)

        _setup_api_key_env("openai:gpt-4o-mini", config)

        assert os.environ.get("OPENAI_API_KEY") == "sk-test123"

    def test_openrouter_model_with_api_key(self, tmp_path):
        """Test setting OPENROUTER_API_KEY from config."""
        config_file = tmp_path / "test.conf"
        config_file.write_text(
            "[testflinger-cli]\nmodel.openrouter.api_key = sk-or-test456\n"
        )

        config = TestflingerCliConfig(config_file)

        # Clear any existing env var
        os.environ.pop("OPENROUTER_API_KEY", None)

        _setup_api_key_env("openrouter:claude-3.5-sonnet", config)

        assert os.environ.get("OPENROUTER_API_KEY") == "sk-or-test456"

    def test_github_copilot_model_with_api_key(self, tmp_path, monkeypatch):
        """Read the Copilot token from config for Copilot models."""
        config_file = tmp_path / "test.conf"
        config_file.write_text(
            "[testflinger-cli]\n"
            "model.github-copilot.api_key = gho-copilot-test\n"
        )
        config = TestflingerCliConfig(config_file)
        monkeypatch.delenv("GITHUB_COPILOT_API_KEY", raising=False)

        _setup_api_key_env("github-copilot:claude-haiku-4.5", config)

        assert os.environ["GITHUB_COPILOT_API_KEY"] == "gho-copilot-test"

    def test_github_copilot_env_token_takes_precedence(
        self, tmp_path, monkeypatch
    ):
        """Keep a token provided by gh auth token instead of config value."""
        config_file = tmp_path / "test.conf"
        config_file.write_text(
            "[testflinger-cli]\n"
            "model.github-copilot.api_key = stale-config-token\n"
        )
        config = TestflingerCliConfig(config_file)
        monkeypatch.setenv("GITHUB_COPILOT_API_KEY", "gh-oauth-token")

        _setup_api_key_env("github-copilot:claude-haiku-4.5", config)

        assert os.environ["GITHUB_COPILOT_API_KEY"] == "gh-oauth-token"

    def test_github_copilot_uses_gh_auth_token(self, tmp_path, monkeypatch):
        """Discover a Copilot token from GitHub CLI when config is empty."""
        config_file = tmp_path / "test.conf"
        config_file.write_text("[testflinger-cli]\n")
        config = TestflingerCliConfig(config_file)
        monkeypatch.delenv("GITHUB_COPILOT_API_KEY", raising=False)

        with patch(
            "testflinger_cli.find.subprocess.run",
            return_value=subprocess.CompletedProcess(
                args=["gh"], returncode=0, stdout="gh-oauth-token\n", stderr=""
            ),
        ) as gh_run:
            _setup_api_key_env("github-copilot:claude-haiku-4.5", config)

        assert os.environ["GITHUB_COPILOT_API_KEY"] == "gh-oauth-token"
        gh_run.assert_called_once_with(
            ["gh", "auth", "token", "--hostname", "github.com"],
            check=True,
            capture_output=True,
            text=True,
        )

    def test_github_copilot_missing_gh_has_actionable_guidance(
        self, tmp_path, monkeypatch
    ):
        """Explain how to authenticate if gh is missing or not logged in."""
        config_file = tmp_path / "test.conf"
        config_file.write_text("[testflinger-cli]\n")
        config = TestflingerCliConfig(config_file)
        monkeypatch.delenv("GITHUB_COPILOT_API_KEY", raising=False)

        with (
            patch(
                "testflinger_cli.find.subprocess.run",
                side_effect=FileNotFoundError,
            ),
            pytest.raises(
                ValueError, match="gh auth login --hostname github.com"
            ),
        ):
            _setup_api_key_env("github-copilot:claude-haiku-4.5", config)


def test_copilot_show_models_lists_chat_completion_ids(monkeypatch, capsys):
    """Copilot model listing includes only IDs usable by Pydantic AI."""
    response = MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps(
        {
            "data": [
                {
                    "id": "claude-haiku-4.5",
                    "supported_endpoints": ["/chat/completions"],
                },
                {
                    "id": "grok-model",
                    "supported_endpoints": ["/responses"],
                },
            ]
        }
    ).encode()
    urlopen = MagicMock(return_value=response)
    monkeypatch.setattr("urllib.request.urlopen", urlopen)

    _fetch_copilot_models("gh-oauth-token")

    request = urlopen.call_args.args[0]
    assert request.full_url == "https://api.githubcopilot.com/models"
    assert request.get_header("Authorization") == "Bearer gh-oauth-token"
    assert request.get_header("Copilot-integration-id") == "vscode-chat"
    output = capsys.readouterr().out
    assert "github-copilot:claude-haiku-4.5" in output
    assert "grok-model" not in output

    def test_ollama_model_with_api_key(self, tmp_path):
        """Test setting OLLAMA_API_KEY from config."""
        config_file = tmp_path / "test.conf"
        config_file.write_text(
            "[testflinger-cli]\nmodel.ollama.api_key = optional-key\n"
        )

        config = TestflingerCliConfig(config_file)

        # Clear any existing env var
        os.environ.pop("OLLAMA_API_KEY", None)

        _setup_api_key_env("ollama:llama2", config)

        assert os.environ.get("OLLAMA_API_KEY") == "optional-key"

    def test_no_api_key_in_config(self, tmp_path):
        """Test graceful handling when API key not in config."""
        config_file = tmp_path / "test.conf"
        config_file.write_text("[testflinger-cli]\n")

        config = TestflingerCliConfig(config_file)

        # Clear any existing env var
        os.environ.pop("OPENAI_API_KEY", None)

        # Should not raise, just skip setting env var
        _setup_api_key_env("openai:gpt-4o-mini", config)

        # Env var should still be unset
        assert "OPENAI_API_KEY" not in os.environ


class TestFindQueuesIntegration:
    """Integration tests for find_queues (mocked)."""

    def test_find_queues_callable(self, tmp_path):
        """Test that find_queues is callable and accepts config."""
        from testflinger_cli.find import find_queues

        # Verify the function signature works and accepts config
        assert callable(find_queues)

    def test_mcp_find_requires_live_agent_records(self):
        """MCP-backed matching uses agents, not curated queues."""
        with pytest.raises(ValueError, match="live Testflinger agent data"):
            find_queues(
                "pi4",
                mcp_cfg=MCPServerConfig(label="mcp", transport="stdio"),
                live_queues=[],
            )
