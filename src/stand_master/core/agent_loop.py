"""STAR PLATINUM（白金之星）— Main ReAct agent loop.

STAR PLATINUM is the primary orchestrator.  It processes user input,
decides whether to handle tasks directly or summon specialised Stands
via GOLD EXPERIENCE, and synthesises all results into a final answer.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from stand_master.config import AgentConfig
from stand_master.core.context_manager import ContextManager
from stand_master.core.prompt_engine import build_system_prompt
from stand_master.memory.store import MemoryStore
from stand_master.mcp.tool_registry import ToolRegistry
from stand_master.services.permission import PermissionManager, PermissionVerdict
from stand_master.stands.base import StandStatus, STAND_PROFILES
from stand_master.stands.gold_experience import GoldExperience

logger = logging.getLogger(__name__)

_SUMMON_TOOL = "summon_stand"


class ChatModel(Protocol):
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
    """STAR PLATINUM —「オラオラオラ！」"""

    def __init__(
        self,
        llm: ChatModel,
        tool_registry: ToolRegistry,
        memory: MemoryStore,
        permissions: PermissionManager,
        config: AgentConfig,
        gold_experience: GoldExperience,
    ) -> None:
        self._llm = llm
        self._tools = tool_registry
        self._memory = memory
        self._permissions = permissions
        self._config = config
        self._context = ContextManager(max_tokens=config.session.max_history_tokens)
        self._arrow = gold_experience

    async def run(self, user_input: str, *, max_steps: int = 15) -> AgentResult:
        memories = self._memory.recall(user_input, top_k=5)
        stand_descriptions = GoldExperience.describe_stands()

        system_prompt = build_system_prompt(
            tool_descriptions=self._tools.get_tool_descriptions(),
            memories=memories,
            stand_descriptions=stand_descriptions,
        )

        self._context.clear()
        self._context.add_message({"role": "system", "content": system_prompt})
        self._context.add_message({"role": "user", "content": user_input})

        tool_records: list[ToolCallRecord] = []
        stands_used: list[str] = []

        for step in range(max_steps):
            response = self._llm.invoke(self._context.get_messages())
            tool_calls = _extract_tool_calls(response)

            if not tool_calls:
                answer = _extract_text(response)
                self._context.add_message({"role": "assistant", "content": answer})
                if self._config.memory.auto_memorize and tool_records:
                    self._memory.store(
                        f"Q: {user_input}\nA: {answer}",
                        {"type": "conversation", "tools_used": [t.name for t in tool_records]},
                    )
                return AgentResult(answer=answer, tool_calls=tool_records, steps=step + 1, stands_used=stands_used)

            self._context.add_message({
                "role": "assistant", "content": _extract_text(response), "tool_calls": tool_calls,
            })

            for tc in tool_calls:
                tool_name = tc["name"]
                tool_args = tc.get("arguments", {})

                # Stand summoning
                if tool_name == _SUMMON_TOOL:
                    result = await self._handle_stand_summon(tool_args)
                    stands_used.append(tool_args.get("stand_type", "unknown"))
                    self._context.add_message({"role": "tool", "content": result, "tool_call_id": tc.get("id", "")})
                    tool_records.append(ToolCallRecord(name=tool_name, arguments=tool_args, result=result))
                    continue

                # Permission check
                perm = self._permissions.check(tool_name, tool_args)
                if perm.verdict == PermissionVerdict.DENY:
                    obs = f"[Permission denied] {perm.reason}"
                    self._context.add_message({"role": "tool", "content": obs, "tool_call_id": tc.get("id", "")})
                    tool_records.append(ToolCallRecord(name=tool_name, arguments=tool_args, result=obs))
                    continue
                if perm.verdict == PermissionVerdict.ASK_USER:
                    obs = f"[Requires confirmation] Tool '{tool_name}' needs user approval."
                    self._context.add_message({"role": "tool", "content": obs, "tool_call_id": tc.get("id", "")})
                    tool_records.append(ToolCallRecord(name=tool_name, arguments=tool_args, result=obs))
                    continue

                # Regular tool execution
                result = await self._tools.call(tool_name, tool_args)
                result = ContextManager.truncate_tool_result(result)
                self._context.add_message({"role": "tool", "content": result, "tool_call_id": tc.get("id", "")})
                tool_records.append(ToolCallRecord(name=tool_name, arguments=tool_args, result=result))

        return AgentResult(
            answer="Error: exceeded maximum steps without reaching a final answer.",
            tool_calls=tool_records, steps=max_steps, stands_used=stands_used,
        )

    async def _handle_stand_summon(self, args: dict[str, Any]) -> str:
        stand_type_str = args.get("stand_type", "")
        task = args.get("task", "")
        context = args.get("context", {})

        if not stand_type_str:
            return "[GOLD EXPERIENCE] Error: stand_type is required."
        if not task:
            return "[GOLD EXPERIENCE] Error: task description is required."

        try:
            stand = self._arrow.summon_by_name(stand_type_str)
        except ValueError as e:
            return f"[GOLD EXPERIENCE] Error: {e}"

        profile = STAND_PROFILES[stand.stand_type]
        logger.info("STAR PLATINUM summons %s for task: %s", profile["name"], task[:80])

        result = await stand.execute(task, context=context)

        if result.status == StandStatus.RETIRED:
            return f"[{profile['name']}] Task completed.\nOutput: {result.output}"
        return f"[{profile['name']}] Task failed.\nError: {result.error}"


def _extract_tool_calls(response: Any) -> list[dict[str, Any]]:
    if hasattr(response, "tool_calls") and response.tool_calls:
        calls = []
        for tc in response.tool_calls:
            if isinstance(tc, dict):
                calls.append(tc)
            elif hasattr(tc, "name"):
                calls.append({"id": getattr(tc, "id", ""), "name": tc.name, "arguments": getattr(tc, "args", {})})
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
            calls.append({"id": tc.get("id", ""), "name": func.get("name", ""), "arguments": args})
        return calls

    return []


def _extract_text(response: Any) -> str:
    if hasattr(response, "content"):
        return str(response.content)
    return str(response)
