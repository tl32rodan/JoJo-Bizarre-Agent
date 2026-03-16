"""MCP client manager for connecting to external MCP servers via stdio."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from react_agent.config import MCPServerConfig

logger = logging.getLogger(__name__)


class ServerNotFoundError(KeyError):
    """Raised when the requested MCP server is not connected."""


@dataclass(frozen=True)
class ToolInfo:
    server_name: str
    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)


@dataclass
class _ServerConnection:
    name: str
    config: MCPServerConfig
    session: Any = None  # mcp.ClientSession
    _context_stack: Any = None  # contextmanager


class MCPClientManager:
    """Manage stdio connections to multiple MCP servers."""

    def __init__(self) -> None:
        self._connections: dict[str, _ServerConnection] = {}

    @property
    def server_names(self) -> list[str]:
        return list(self._connections.keys())

    async def connect_all(
        self, configs: dict[str, MCPServerConfig], *, max_retries: int = 3,
    ) -> None:
        """Spawn each MCP server process and establish a session."""
        for name, config in configs.items():
            await self._connect_one(name, config, max_retries=max_retries)

    async def _connect_one(
        self, name: str, config: MCPServerConfig, *, max_retries: int = 3,
    ) -> None:
        from mcp import StdioServerParameters
        from mcp.client.stdio import stdio_client
        from mcp import ClientSession

        params = StdioServerParameters(
            command=config.command,
            args=config.args,
            env=config.env or None,
        )

        last_exc: Exception | None = None
        for attempt in range(max_retries):
            try:
                # stdio_client returns an async context manager yielding (read, write) streams
                ctx = stdio_client(params)
                streams = await ctx.__aenter__()
                read_stream, write_stream = streams
                session = ClientSession(read_stream, write_stream)
                await session.__aenter__()
                await session.initialize()

                conn = _ServerConnection(name=name, config=config, session=session, _context_stack=ctx)
                self._connections[name] = conn
                logger.info("Connected to MCP server '%s'", name)
                return
            except Exception as exc:
                last_exc = exc
                delay = 2 ** attempt
                logger.warning(
                    "Failed to connect to '%s' (attempt %d/%d): %s. Retrying in %ds.",
                    name, attempt + 1, max_retries, exc, delay,
                )
                await asyncio.sleep(delay)

        logger.error("Could not connect to MCP server '%s' after %d attempts", name, max_retries)
        if last_exc:
            raise ConnectionError(
                f"Failed to connect to MCP server '{name}': {last_exc}"
            ) from last_exc

    async def list_tools(self, server_name: str | None = None) -> list[ToolInfo]:
        """List tools from one or all connected servers."""
        servers = (
            [self._get(server_name)] if server_name else list(self._connections.values())
        )
        all_tools: list[ToolInfo] = []
        for conn in servers:
            try:
                result = await conn.session.list_tools()
                for tool in result.tools:
                    all_tools.append(ToolInfo(
                        server_name=conn.name,
                        name=tool.name,
                        description=tool.description or "",
                        input_schema=tool.inputSchema if hasattr(tool, "inputSchema") else {},
                    ))
            except Exception:
                logger.exception("Failed to list tools from '%s'", conn.name)
        return all_tools

    async def call_tool(
        self, server_name: str, tool_name: str, arguments: dict[str, Any],
    ) -> str:
        """Call a tool on a specific MCP server and return the text result."""
        conn = self._get(server_name)
        result = await conn.session.call_tool(tool_name, arguments)
        # MCP returns content blocks; concatenate text parts.
        parts = []
        for block in result.content:
            if hasattr(block, "text"):
                parts.append(block.text)
        return "\n".join(parts)

    async def disconnect_all(self) -> None:
        """Gracefully close all MCP server connections."""
        for conn in list(self._connections.values()):
            try:
                if conn.session is not None:
                    await conn.session.__aexit__(None, None, None)
                if conn._context_stack is not None:
                    await conn._context_stack.__aexit__(None, None, None)
            except Exception:
                logger.exception("Error disconnecting from '%s'", conn.name)
        self._connections.clear()

    def _get(self, name: str) -> _ServerConnection:
        try:
            return self._connections[name]
        except KeyError:
            raise ServerNotFoundError(f"MCP server '{name}' is not connected.") from None
