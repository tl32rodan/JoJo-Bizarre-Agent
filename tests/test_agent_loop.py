"""Tests for react_agent.core.agent_loop."""

from __future__ import annotations

import pytest

from react_agent.config import AgentConfig, PermissionConfig, MemoryConfig
from react_agent.core.agent_loop import AgentLoop, AgentResult
from react_agent.mcp.tool_registry import ToolEntry, ToolRegistry
from react_agent.services.permission import PermissionManager
from react_agent.memory.store import MemoryStore
from conftest import FakeLLM, FakeLLMResponse, FakeVectorStore, FakeEmbedding


def _make_registry_with_echo() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(ToolEntry(
        name="echo",
        description="Echo back the input",
        source="local",
        fn=lambda text="": f"echoed: {text}",
    ))
    return reg


class TestAgentLoop:
    @pytest.mark.asyncio
    async def test_simple_answer_no_tool(self):
        llm = FakeLLM(responses=[
            FakeLLMResponse(content="The answer is 42."),
        ])
        agent = AgentLoop(llm=llm, tool_registry=ToolRegistry())
        result = await agent.run("What is the answer?")
        assert result.answer == "The answer is 42."
        assert result.tool_calls == []
        assert result.steps == 1

    @pytest.mark.asyncio
    async def test_tool_call_and_observation(self):
        # First response: tool call. Second response: final answer.
        llm = FakeLLM(responses=[
            FakeLLMResponse(content="", tool_calls=[
                {"id": "tc1", "name": "echo", "args": {"text": "hello"}},
            ]),
            FakeLLMResponse(content="The tool said: echoed: hello"),
        ])
        reg = _make_registry_with_echo()
        agent = AgentLoop(llm=llm, tool_registry=reg)
        result = await agent.run("Echo hello")
        assert "echoed: hello" in result.answer
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "echo"
        assert result.steps == 2

    @pytest.mark.asyncio
    async def test_permission_denied_skips_tool(self):
        llm = FakeLLM(responses=[
            FakeLLMResponse(content="", tool_calls=[
                {"id": "tc1", "name": "echo", "args": {"text": "x"}},
            ]),
            FakeLLMResponse(content="Permission was denied."),
        ])
        reg = _make_registry_with_echo()
        perms = PermissionManager(PermissionConfig(mode="deny_all"))
        agent = AgentLoop(llm=llm, tool_registry=reg, permissions=perms)
        result = await agent.run("Echo something")
        assert len(result.tool_calls) == 1
        assert "denied" in result.tool_calls[0].result.lower()

    @pytest.mark.asyncio
    async def test_memory_recall_injected(self):
        vs = FakeVectorStore()
        emb = FakeEmbedding()
        mem = MemoryStore(vector_store=vs, embedder=emb)
        mem.store("Python was created by Guido", {"type": "fact"})

        llm = FakeLLM(responses=[
            FakeLLMResponse(content="Based on memory, Python was created by Guido."),
        ])
        agent = AgentLoop(llm=llm, tool_registry=ToolRegistry(), memory=mem)
        result = await agent.run("Who created Python?")
        # Check that the system prompt included memory.
        system_msg = llm.invocations[0][0]
        assert "Guido" in system_msg["content"]

    @pytest.mark.asyncio
    async def test_max_steps_reached(self):
        # LLM always returns tool calls, never a final answer.
        responses = [
            FakeLLMResponse(content="", tool_calls=[
                {"id": f"tc{i}", "name": "echo", "args": {"text": "loop"}},
            ])
            for i in range(20)
        ]
        llm = FakeLLM(responses=responses)
        reg = _make_registry_with_echo()
        agent = AgentLoop(llm=llm, tool_registry=reg)
        result = await agent.run("Loop forever", max_steps=3)
        assert "exceeded" in result.answer.lower()
        assert result.steps == 3

    @pytest.mark.asyncio
    async def test_tool_error_as_observation(self):
        def failing_tool(**kwargs) -> str:
            raise RuntimeError("Tool broke")

        reg = ToolRegistry()
        reg.register(ToolEntry(
            name="bad_tool", description="Fails", source="local",
            fn=failing_tool,
        ))
        llm = FakeLLM(responses=[
            FakeLLMResponse(content="", tool_calls=[
                {"id": "tc1", "name": "bad_tool", "args": {}},
            ]),
            FakeLLMResponse(content="Tool failed, I'll try something else."),
        ])
        agent = AgentLoop(llm=llm, tool_registry=reg)
        result = await agent.run("Use bad tool")
        assert len(result.tool_calls) == 1
        assert "error" in result.tool_calls[0].result.lower()

    @pytest.mark.asyncio
    async def test_result_auto_memorized(self):
        vs = FakeVectorStore()
        emb = FakeEmbedding()
        mem = MemoryStore(
            vector_store=vs, embedder=emb,
            config=MemoryConfig(auto_memorize=True),
        )
        llm = FakeLLM(responses=[
            FakeLLMResponse(content="", tool_calls=[
                {"id": "tc1", "name": "echo", "args": {"text": "test"}},
            ]),
            FakeLLMResponse(content="Done with tool."),
        ])
        reg = _make_registry_with_echo()
        agent = AgentLoop(llm=llm, tool_registry=reg, memory=mem)
        await agent.run("Do something")
        # Memory should have been stored (persist called).
        assert vs.persist_count >= 1
