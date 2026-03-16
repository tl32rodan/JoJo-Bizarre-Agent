"""Unified tool registry combining SMAK (direct Python) and MCP tools."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from react_agent.mcp.client import MCPClientManager, ToolInfo
from react_agent.mcp.skill_loader import SkillInfo

logger = logging.getLogger(__name__)


@dataclass
class ToolEntry:
    """A registered tool with metadata and callable."""

    name: str
    description: str
    source: str  # "smak", "mcp:<server_name>", or "local"
    input_schema: dict[str, Any] = field(default_factory=dict)
    fn: Callable[..., Any] | None = None  # sync or async callable
    is_async: bool = False


class ToolRegistry:
    """Manage tools from multiple sources: SMAK (direct), MCP servers, local."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolEntry] = {}

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())

    def get(self, name: str) -> ToolEntry | None:
        return self._tools.get(name)

    def register(self, entry: ToolEntry) -> None:
        """Register a tool. Prefixes name if collision detected."""
        name = entry.name
        if name in self._tools:
            # Prefix with source to avoid collision.
            name = f"{entry.source}:{entry.name}"
            entry = ToolEntry(
                name=name,
                description=entry.description,
                source=entry.source,
                input_schema=entry.input_schema,
                fn=entry.fn,
                is_async=entry.is_async,
            )
        self._tools[name] = entry

    def register_callable(
        self,
        name: str,
        fn: Callable[..., Any],
        *,
        description: str = "",
        source: str = "local",
        is_async: bool = False,
    ) -> None:
        """Convenience method to register a plain callable as a tool."""
        self.register(ToolEntry(
            name=name,
            description=description or (fn.__doc__ or ""),
            source=source,
            fn=fn,
            is_async=is_async,
        ))

    async def register_mcp_tools(self, mcp_client: MCPClientManager) -> None:
        """Discover and register all tools from connected MCP servers."""
        all_tools = await mcp_client.list_tools()
        for tool_info in all_tools:
            server = tool_info.server_name

            async def _make_caller(srv: str, tn: str) -> Callable[..., Awaitable[str]]:
                async def call(**kwargs: Any) -> str:
                    return await mcp_client.call_tool(srv, tn, kwargs)
                return call

            caller = await _make_caller(server, tool_info.name)
            self.register(ToolEntry(
                name=tool_info.name,
                description=tool_info.description,
                source=f"mcp:{server}",
                input_schema=tool_info.input_schema,
                fn=caller,
                is_async=True,
            ))

    def enhance_with_skills(self, skills: list[SkillInfo]) -> None:
        """Merge SKILL.md tool hints into existing tool descriptions."""
        for skill in skills:
            for tool_name, hint in skill.tool_hints.items():
                entry = self._tools.get(tool_name)
                if entry is not None and hint:
                    self._tools[tool_name] = ToolEntry(
                        name=entry.name,
                        description=f"{entry.description}\nHint: {hint}",
                        source=entry.source,
                        input_schema=entry.input_schema,
                        fn=entry.fn,
                        is_async=entry.is_async,
                    )

    def get_tool_descriptions(self) -> str:
        """Format all tools as text for LLM system prompt."""
        lines: list[str] = []
        for entry in self._tools.values():
            lines.append(f"- **{entry.name}** ({entry.source}): {entry.description}")
        return "\n".join(lines)

    async def call(self, name: str, arguments: dict[str, Any]) -> str:
        """Execute a tool by name."""
        entry = self._tools.get(name)
        if entry is None:
            return f"Error: Tool '{name}' not found."
        if entry.fn is None:
            return f"Error: Tool '{name}' has no callable."
        try:
            if entry.is_async:
                result = await entry.fn(**arguments)
            else:
                result = entry.fn(**arguments)
            return str(result)
        except Exception as exc:
            return f"Error executing tool '{name}': {exc}"
