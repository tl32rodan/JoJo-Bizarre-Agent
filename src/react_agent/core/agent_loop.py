"""STAR PLATINUM（白金之星）— Main ReAct agent loop.

STAR PLATINUM is the primary orchestrator.  It processes user input,
decides whether to handle tasks directly or summon specialised Stands
via the Stand Arrow, and synthesises all results into a final answer.
"""

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
from react_agent.stands.base import StandType, StandResult, StandStatus, STAND_PROFILES
from react_agent.stands.arrow import StandArrow

logger = logging.getLogger(__name__)

# Stand-summoning tool name exposed to the LLM via bind_tools().
_SUMMON_TOOL = "summon_stand"


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
    stands_used: list[str] = field(default_factory=list)


class AgentLoop:
    """STAR PLATINUM — 「オラオラオラ！」

    The main ReAct orchestrator with the ability to summon Stands
    through the Stand Arrow for specialised tasks.
    """

    def __init__(
        self,
        llm: ChatModel,
        tool_registry: ToolRegistry,
        memory: MemoryStore | None = None,
        permissions: PermissionManager | None = None,
        config: AgentConfig | None = None,
        stand_arrow: StandArrow | None = None,
    ) -> None:
        self._llm = llm
        self._tools = tool_registry
        self._memory = memory
        self._permissions = permissions
        self._config = config or AgentConfig()
        self._context = ContextManager(max_tokens=self._config.session.max_history_tokens)
        self._arrow = stand_arrow

    async def run(self, user_input: str, *, max_steps: int = 15) -> AgentResult:
        """Execute the STAR PLATINUM ReAct loop for a single user query."""
        # 1. Recall relevant memories.
        memories = None
        if self._memory is not None:
            memories = self._memory.recall(user_input, top_k=5)

        # 2. Build system prompt (now includes Stand descriptions).
        stand_descriptions = StandArrow.describe_stands() if self._arrow else ""
        system_prompt = build_system_prompt(
            tool_descriptions=self._tools.get_tool_descriptions(),
            memories=memories,
            stand_descriptions=stand_descriptions,
        )

        # 3. Reset context for this query.
        self._context.clear()
        self._context.add_message({"role": "system", "content": system_prompt})
        self._context.add_message({"role": "user", "content": user_input})

        tool_records: list[ToolCallRecord] = []
        stands_used: list[str] = []

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

                return AgentResult(
                    answer=answer,
                    tool_calls=tool_records,
                    steps=step + 1,
                    stands_used=stands_used,
                )

            # 6. Execute tool calls.
            self._context.add_message({
                "role": "assistant",
                "content": _extract_text(response),
                "tool_calls": tool_calls,
            })

            for tc in tool_calls:
                tool_name = tc["name"]
                tool_args = tc.get("arguments", {})

                # ── Stand summoning ──
                if tool_name == _SUMMON_TOOL and self._arrow is not None:
                    result = await self._handle_stand_summon(tool_args)
                    stand_name = tool_args.get("stand_type", "unknown")
                    stands_used.append(stand_name)
                    self._context.add_message({
                        "role": "tool",
                        "content": result,
                        "tool_call_id": tc.get("id", ""),
                    })
                    tool_records.append(ToolCallRecord(
                        name=tool_name, arguments=tool_args, result=result,
                    ))
                    continue

                # ── Permission check ──
                if self._permissions is not None:
                    perm = self._permissions.check(tool_name, tool_args)
                    if perm.verdict == PermissionVerdict.DENY:
                        observation = f"[Permission denied] {perm.reason}"
                        self._context.add_message({"role": "tool", "content": observation, "tool_call_id": tc.get("id", "")})
                        tool_records.append(ToolCallRecord(name=tool_name, arguments=tool_args, result=observation))
                        continue
                    if perm.verdict == PermissionVerdict.ASK_USER:
                        observation = f"[Requires confirmation] Tool '{tool_name}' needs user approval."
                        self._context.add_message({"role": "tool", "content": observation, "tool_call_id": tc.get("id", "")})
                        tool_records.append(ToolCallRecord(name=tool_name, arguments=tool_args, result=observation))
                        continue

                # ── Regular tool execution ──
                result = await self._tools.call(tool_name, tool_args)
                result = ContextManager.truncate_tool_result(result)

                self._context.add_message({"role": "tool", "content": result, "tool_call_id": tc.get("id", "")})
                tool_records.append(ToolCallRecord(name=tool_name, arguments=tool_args, result=result))

        return AgentResult(
            answer="Error: exceeded maximum steps without reaching a final answer.",
            tool_calls=tool_records,
            steps=max_steps,
            stands_used=stands_used,
        )

    async def _handle_stand_summon(self, args: dict[str, Any]) -> str:
        """Summon a Stand via the Arrow and execute its ability."""
        stand_type_str = args.get("stand_type", "")
        task = args.get("task", "")
        context = args.get("context", {})

        if not stand_type_str:
            return "[Stand Arrow] Error: stand_type is required."
        if not task:
            return "[Stand Arrow] Error: task description is required."

        try:
            stand = self._arrow.summon_by_name(stand_type_str)
        except ValueError as e:
            return f"[Stand Arrow] Error: {e}"

        profile = STAND_PROFILES[stand.stand_type]
        logger.info(
            "STAR PLATINUM summons %s for task: %s",
            profile["name"], task[:80],
        )

        result: StandResult = await stand.execute(task, context=context)

        if result.status == StandStatus.RETIRED:
            return (
                f"[{profile['name']}] Task completed successfully.\n"
                f"Output: {result.output}"
            )
        else:
            return (
                f"[{profile['name']}] Task failed.\n"
                f"Error: {result.error}"
            )


def _extract_tool_calls(response: Any) -> list[dict[str, Any]]:
    """Extract tool calls from an LLM response (LangChain format)."""
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
