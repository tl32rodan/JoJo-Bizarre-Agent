"""Main ReAct agent loop with structured tool calling."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from react_agent.config import AgentConfig
from react_agent.core.context_manager import ContextManager
from react_agent.core.prompt_engine import build_system_prompt
from react_agent.memory.store import MemoryStore
from react_agent.mcp.tool_registry import ToolRegistry
from react_agent.services.permission import PermissionManager, PermissionVerdict

logger = logging.getLogger(__name__)


class ChatModel(Protocol):
    """Minimal interface for a chat model supporting tool calling.

    Compatible with langchain_openai.ChatOpenAI after bind_tools().
    """

    def invoke(self, messages: list[dict[str, Any]]) -> Any: ...
    def bind_tools(self, tools: list[Any]) -> ChatModel: ...


@dataclass(frozen=True)
class ToolCallRecord:
    name: str
    arguments: dict[str, Any]
    result: str


@dataclass(frozen=True)
class AgentResult:
    answer: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    steps: int = 0


class AgentLoop:
    """ReAct agent with structured tool calling via ChatOpenAI.bind_tools()."""

    def __init__(
        self,
        llm: ChatModel,
        tool_registry: ToolRegistry,
        memory: MemoryStore | None = None,
        permissions: PermissionManager | None = None,
        config: AgentConfig | None = None,
    ) -> None:
        self._llm = llm
        self._tools = tool_registry
        self._memory = memory
        self._permissions = permissions
        self._config = config or AgentConfig()
        self._context = ContextManager(max_tokens=self._config.session.max_history_tokens)

    async def run(self, user_input: str, *, max_steps: int = 15) -> AgentResult:
        """Execute the ReAct loop for a single user query."""
        # 1. Recall relevant memories.
        memories = None
        if self._memory is not None:
            memories = self._memory.recall(user_input, top_k=5)

        # 2. Build system prompt.
        system_prompt = build_system_prompt(
            tool_descriptions=self._tools.get_tool_descriptions(),
            memories=memories,
        )

        # 3. Reset context for this query.
        self._context.clear()
        self._context.add_message({"role": "system", "content": system_prompt})
        self._context.add_message({"role": "user", "content": user_input})

        tool_records: list[ToolCallRecord] = []

        for step in range(max_steps):
            messages = self._context.get_messages()

            # 4. Call LLM.
            response = self._llm.invoke(messages)

            # 5. Check for tool calls (structured).
            tool_calls = _extract_tool_calls(response)

            if not tool_calls:
                # No tool calls — this is the final answer.
                answer = _extract_text(response)
                self._context.add_message({"role": "assistant", "content": answer})

                # Auto-memorize.
                if self._memory and self._config.memory.auto_memorize and tool_records:
                    self._memory.store(
                        f"Q: {user_input}\nA: {answer}",
                        {"type": "conversation", "tools_used": [t.name for t in tool_records]},
                    )

                return AgentResult(answer=answer, tool_calls=tool_records, steps=step + 1)

            # 6. Execute tool calls.
            # Record assistant message with tool_calls.
            self._context.add_message({
                "role": "assistant",
                "content": _extract_text(response),
                "tool_calls": tool_calls,
            })

            for tc in tool_calls:
                tool_name = tc["name"]
                tool_args = tc.get("arguments", {})

                # Permission check.
                if self._permissions is not None:
                    perm = self._permissions.check(tool_name, tool_args)
                    if perm.verdict == PermissionVerdict.DENY:
                        observation = f"[Permission denied] {perm.reason}"
                        self._context.add_message({"role": "tool", "content": observation, "tool_call_id": tc.get("id", "")})
                        tool_records.append(ToolCallRecord(name=tool_name, arguments=tool_args, result=observation))
                        continue
                    if perm.verdict == PermissionVerdict.ASK_USER:
                        # In non-interactive mode, skip with a note.
                        observation = f"[Requires confirmation] Tool '{tool_name}' needs user approval."
                        self._context.add_message({"role": "tool", "content": observation, "tool_call_id": tc.get("id", "")})
                        tool_records.append(ToolCallRecord(name=tool_name, arguments=tool_args, result=observation))
                        continue

                # Execute tool.
                result = await self._tools.call(tool_name, tool_args)
                result = ContextManager.truncate_tool_result(result)

                self._context.add_message({"role": "tool", "content": result, "tool_call_id": tc.get("id", "")})
                tool_records.append(ToolCallRecord(name=tool_name, arguments=tool_args, result=result))

        return AgentResult(
            answer="Error: exceeded maximum steps without reaching a final answer.",
            tool_calls=tool_records,
            steps=max_steps,
        )


def _extract_tool_calls(response: Any) -> list[dict[str, Any]]:
    """Extract tool calls from an LLM response (LangChain format)."""
    # LangChain ChatOpenAI returns AIMessage with .tool_calls
    if hasattr(response, "tool_calls") and response.tool_calls:
        calls = []
        for tc in response.tool_calls:
            if isinstance(tc, dict):
                calls.append(tc)
            elif hasattr(tc, "name"):
                calls.append({
                    "id": getattr(tc, "id", ""),
                    "name": tc.name,
                    "arguments": getattr(tc, "args", {}),
                })
        return calls

    # Fallback: check for additional_kwargs.tool_calls (raw OpenAI format)
    if hasattr(response, "additional_kwargs"):
        raw = response.additional_kwargs.get("tool_calls", [])
        calls = []
        for tc in raw:
            func = tc.get("function", {})
            args = func.get("arguments", "{}")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {"raw": args}
            calls.append({
                "id": tc.get("id", ""),
                "name": func.get("name", ""),
                "arguments": args,
            })
        return calls

    return []


def _extract_text(response: Any) -> str:
    """Extract text content from an LLM response."""
    if hasattr(response, "content"):
        return str(response.content)
    return str(response)
