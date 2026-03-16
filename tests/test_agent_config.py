"""Tests for react_agent.config."""

from __future__ import annotations

from pathlib import Path

import pytest

from react_agent.config import (
    AgentConfig,
    LLMConfig,
    MCPServerConfig,
    MemoryConfig,
    PermissionConfig,
    load_agent_config,
)


class TestLoadAgentConfig:
    def test_missing_yaml_returns_defaults(self, tmp_path):
        cfg = load_agent_config(tmp_path / "nonexistent.yaml")
        assert isinstance(cfg, AgentConfig)
        assert cfg.llm.model == "gpt-oss-120b"

    def test_load_full_yaml(self, tmp_path):
        yaml_file = tmp_path / "agent.yaml"
        yaml_file.write_text(
            """
llm:
  base_url: http://localhost:8000/v1
  model: test-model
  api_key: test-key
memory:
  index_name: my_memory
  max_entries: 500
mcp_servers:
  fs:
    command: python
    args: ["-m", "fs_server"]
    env:
      ROOT_DIR: /tmp
permissions:
  mode: allow_all
  denied_tools: ["delete_file"]
""",
            encoding="utf-8",
        )
        cfg = load_agent_config(yaml_file)
        assert cfg.llm.base_url == "http://localhost:8000/v1"
        assert cfg.llm.model == "test-model"
        assert cfg.memory.index_name == "my_memory"
        assert cfg.memory.max_entries == 500
        assert "fs" in cfg.mcp_servers
        assert cfg.mcp_servers["fs"].command == "python"
        assert cfg.mcp_servers["fs"].env == {"ROOT_DIR": "/tmp"}
        assert cfg.permissions.mode == "allow_all"
        assert "delete_file" in cfg.permissions.denied_tools

    def test_env_var_substitution(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MY_MODEL", "custom-model")
        yaml_file = tmp_path / "agent.yaml"
        yaml_file.write_text(
            """
llm:
  model: ${MY_MODEL:-fallback}
""",
            encoding="utf-8",
        )
        cfg = load_agent_config(yaml_file)
        assert cfg.llm.model == "custom-model"

    def test_env_var_default_used(self, tmp_path, monkeypatch):
        monkeypatch.delenv("MY_MODEL", raising=False)
        yaml_file = tmp_path / "agent.yaml"
        yaml_file.write_text(
            """
llm:
  model: ${MY_MODEL:-fallback-model}
""",
            encoding="utf-8",
        )
        cfg = load_agent_config(yaml_file)
        assert cfg.llm.model == "fallback-model"

    def test_partial_yaml_merges_defaults(self, tmp_path):
        yaml_file = tmp_path / "agent.yaml"
        yaml_file.write_text(
            """
llm:
  model: partial-model
""",
            encoding="utf-8",
        )
        cfg = load_agent_config(yaml_file)
        assert cfg.llm.model == "partial-model"
        # Other fields should have defaults.
        assert cfg.llm.base_url == "http://f15dtpai1:11517/v1"
        assert cfg.memory.index_name == "agent_memory"

    def test_empty_yaml(self, tmp_path):
        yaml_file = tmp_path / "agent.yaml"
        yaml_file.write_text("", encoding="utf-8")
        cfg = load_agent_config(yaml_file)
        assert isinstance(cfg, AgentConfig)
