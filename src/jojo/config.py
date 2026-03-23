"""Agent configuration loaded from agent.yaml."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import yaml


def _substitute_env_vars(value: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        var_name = match.group(1)
        default = match.group(3)
        return os.environ.get(var_name, default if default is not None else "")
    return re.sub(r"\$\{(\w+)(:-(.*?))?\}", _replace, value)


def _resolve_strings(data: Any) -> Any:
    if isinstance(data, str):
        return _substitute_env_vars(data)
    if isinstance(data, dict):
        return {k: _resolve_strings(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_resolve_strings(item) for item in data]
    return data


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LLMConfig:
    base_url: str = "http://f15dtpai1:11517/v1"
    model: str = "gpt-oss-120b"
    api_key: str = "EMPTY"
    models: dict[str, str] = field(default_factory=lambda: {
        "default": "gpt-oss-120b",
        "reasoning": "qwen3_235B_A22B",
    })


@dataclass(frozen=True)
class EmbeddingConfig:
    api_base: str = "http://f15dtpai1:11434"
    model: str = "nomic-embed-text"


@dataclass(frozen=True)
class SmakLibConfig:
    workspace_config: str = "./workspace_config.yaml"


@dataclass(frozen=True)
class MemoryConfig:
    index_name: str = "agent_memory"
    storage_dir: str = "./agent_data/memory"
    max_entries: int = 10000
    auto_memorize: bool = True


@dataclass(frozen=True)
class MCPServerConfig:
    command: str = "python"
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PermissionConfig:
    mode: str = "ask"
    allowed_tools: list[str] = field(default_factory=lambda: ["*"])
    denied_tools: list[str] = field(default_factory=list)
    require_confirmation: list[str] = field(default_factory=lambda: [
        "delete_file", "write_file", "run_terminal_command",
    ])


@dataclass(frozen=True)
class HeartbeatConfig:
    enabled: bool = True
    interval_seconds: int = 300
    checks: list[str] = field(default_factory=lambda: [
        "llm_health", "mcp_servers_alive", "memory_store_ok",
    ])


@dataclass(frozen=True)
class EmailConfig:
    enabled: bool = False
    ddi_api_path: str = ""
    sender: str = ""
    recipients: list[str] = field(default_factory=list)
    notify_on: list[str] = field(default_factory=lambda: [
        "error", "heartbeat_failure", "task_complete",
    ])


@dataclass(frozen=True)
class OpenCodeConfig:
    enabled: bool = False
    base_url: str = "http://localhost:4096"
    password: str = ""
    default_agent: str = "build"
    timeout_seconds: int = 300


@dataclass(frozen=True)
class SubAgentConfig:
    enabled: bool = True
    mode: str = "tmux"
    backend: str = "tmux"  # "tmux" | "opencode"
    max_concurrent: int = 3
    timeout_seconds: int = 600
    work_dir: str = "./agent_data/subagent_tasks/"


@dataclass(frozen=True)
class SessionConfig:
    max_history_tokens: int = 8000
    auto_summarize_after: int = 20


@dataclass(frozen=True)
class AgentConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    smak: SmakLibConfig = field(default_factory=SmakLibConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    mcp_servers: dict[str, MCPServerConfig] = field(default_factory=dict)
    permissions: PermissionConfig = field(default_factory=PermissionConfig)
    heartbeat: HeartbeatConfig = field(default_factory=HeartbeatConfig)
    email: EmailConfig = field(default_factory=EmailConfig)
    subagent: SubAgentConfig = field(default_factory=SubAgentConfig)
    opencode: OpenCodeConfig = field(default_factory=OpenCodeConfig)
    session: SessionConfig = field(default_factory=SessionConfig)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def _build_dataclass(cls: type, data: Mapping[str, Any]) -> Any:
    known = {f for f in cls.__dataclass_fields__}
    kwargs = {k: v for k, v in data.items() if k in known}
    return cls(**kwargs)


def _parse_mcp_servers(raw: Mapping[str, Any]) -> dict[str, MCPServerConfig]:
    result: dict[str, MCPServerConfig] = {}
    for name, cfg in raw.items():
        if isinstance(cfg, Mapping):
            result[name] = _build_dataclass(MCPServerConfig, cfg)
    return result


def load_agent_config(path: str | Path = "agent.yaml") -> AgentConfig:
    config_path = Path(path)
    if not config_path.exists():
        return AgentConfig()

    raw_text = config_path.read_text(encoding="utf-8")
    data: Any = yaml.safe_load(raw_text)
    if not isinstance(data, Mapping):
        return AgentConfig()

    data = _resolve_strings(data)

    return AgentConfig(
        llm=_build_dataclass(LLMConfig, data["llm"]) if "llm" in data else LLMConfig(),
        embedding=_build_dataclass(EmbeddingConfig, data["embedding"]) if "embedding" in data else EmbeddingConfig(),
        smak=_build_dataclass(SmakLibConfig, data["smak"]) if "smak" in data else SmakLibConfig(),
        memory=_build_dataclass(MemoryConfig, data["memory"]) if "memory" in data else MemoryConfig(),
        mcp_servers=_parse_mcp_servers(data.get("mcp_servers", {})),
        permissions=_build_dataclass(PermissionConfig, data["permissions"]) if "permissions" in data else PermissionConfig(),
        heartbeat=_build_dataclass(HeartbeatConfig, data["heartbeat"]) if "heartbeat" in data else HeartbeatConfig(),
        email=_build_dataclass(EmailConfig, data["email"]) if "email" in data else EmailConfig(),
        subagent=_build_dataclass(SubAgentConfig, data["subagent"]) if "subagent" in data else SubAgentConfig(),
        opencode=_build_dataclass(OpenCodeConfig, data["opencode"]) if "opencode" in data else OpenCodeConfig(),
        session=_build_dataclass(SessionConfig, data["session"]) if "session" in data else SessionConfig(),
    )
