"""Tests for react_agent.mcp.client (mocked, no real MCP servers)."""

from __future__ import annotations

import pytest

from react_agent.mcp.client import MCPClientManager, ServerNotFoundError, ToolInfo


class TestMCPClientManager:
    def test_initial_state(self):
        mgr = MCPClientManager()
        assert mgr.server_names == []

    def test_get_unknown_server_raises(self):
        mgr = MCPClientManager()
        with pytest.raises(ServerNotFoundError):
            mgr._get("nonexistent")

    @pytest.mark.asyncio
    async def test_call_tool_unknown_server_raises(self):
        mgr = MCPClientManager()
        with pytest.raises(ServerNotFoundError):
            await mgr.call_tool("nonexistent", "some_tool", {})

    @pytest.mark.asyncio
    async def test_disconnect_empty_is_safe(self):
        mgr = MCPClientManager()
        await mgr.disconnect_all()  # should not raise

    @pytest.mark.asyncio
    async def test_list_tools_empty(self):
        mgr = MCPClientManager()
        tools = await mgr.list_tools()
        assert tools == []


class TestToolInfo:
    def test_creation(self):
        info = ToolInfo(
            server_name="fs",
            name="read_file",
            description="Read a file",
            input_schema={"type": "object"},
        )
        assert info.server_name == "fs"
        assert info.name == "read_file"
