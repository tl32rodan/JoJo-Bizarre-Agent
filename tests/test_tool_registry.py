"""Tests for react_agent.mcp.tool_registry."""

from __future__ import annotations

import asyncio

import pytest

from react_agent.mcp.tool_registry import ToolEntry, ToolRegistry
from react_agent.mcp.skill_loader import SkillInfo


class TestToolRegistry:
    def test_register_and_get(self):
        reg = ToolRegistry()
        reg.register(ToolEntry(
            name="my_tool",
            description="Does things",
            source="local",
            fn=lambda: "ok",
        ))
        assert "my_tool" in reg.tool_names
        assert reg.get("my_tool") is not None

    def test_collision_uses_prefix(self):
        reg = ToolRegistry()
        reg.register(ToolEntry(name="read_file", description="A", source="local"))
        reg.register(ToolEntry(name="read_file", description="B", source="mcp:fs"))
        assert "read_file" in reg.tool_names
        assert "mcp:fs:read_file" in reg.tool_names

    def test_register_callable(self):
        reg = ToolRegistry()

        def greet(name: str) -> str:
            """Say hello."""
            return f"Hello, {name}!"

        reg.register_callable("greet", greet, source="local")
        assert "greet" in reg.tool_names
        entry = reg.get("greet")
        assert entry.description == "Say hello."

    def test_get_tool_descriptions(self):
        reg = ToolRegistry()
        reg.register(ToolEntry(name="tool_a", description="Desc A", source="local"))
        reg.register(ToolEntry(name="tool_b", description="Desc B", source="mcp:fs"))
        text = reg.get_tool_descriptions()
        assert "tool_a" in text
        assert "tool_b" in text
        assert "Desc A" in text

    def test_enhance_with_skills(self):
        reg = ToolRegistry()
        reg.register(ToolEntry(name="ls", description="List files", source="mcp:fs"))
        skill = SkillInfo(
            name="fs",
            description="",
            body="",
            tool_hints={"ls": "Use to explore directories"},
        )
        reg.enhance_with_skills([skill])
        entry = reg.get("ls")
        assert "Use to explore directories" in entry.description

    @pytest.mark.asyncio
    async def test_call_sync_tool(self):
        reg = ToolRegistry()
        reg.register(ToolEntry(
            name="echo", description="Echo", source="local",
            fn=lambda text="": f"echo: {text}",
        ))
        result = await reg.call("echo", {"text": "hello"})
        assert result == "echo: hello"

    @pytest.mark.asyncio
    async def test_call_async_tool(self):
        reg = ToolRegistry()

        async def async_tool(x: str = "") -> str:
            return f"async: {x}"

        reg.register(ToolEntry(
            name="async_echo", description="Async echo", source="local",
            fn=async_tool, is_async=True,
        ))
        result = await reg.call("async_echo", {"x": "hi"})
        assert result == "async: hi"

    @pytest.mark.asyncio
    async def test_call_unknown_tool(self):
        reg = ToolRegistry()
        result = await reg.call("nonexistent", {})
        assert "not found" in result.lower()
