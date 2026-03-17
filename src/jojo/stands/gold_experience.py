"""GOLD EXPERIENCE（ゴールド・エクスペリエンス）— Life Giver Stand.

Ability: Life Giver — spawns and orchestrates sub-agent Stands.
The only Stand that can summon other Stands as sub-agents.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from jojo.stands.base import (
    Stand, StandProfile, StandResult, StandStatus, StandType,
    STAND_PROFILES,
)

logger = logging.getLogger(__name__)

# Stands that Gold Experience can spawn as sub-agents
SPAWNABLE_TYPES = (
    StandType.THE_WORLD,
    StandType.HIEROPHANT_GREEN,
    StandType.HARVEST,
    StandType.SHEER_HEART_ATTACK,
)


class GoldExperience(Stand):
    """「無駄無駄無駄！」"""

    stand_type = StandType.GOLD_EXPERIENCE

    def __init__(
        self,
        llm: Any,
        tool_registry: Any,
        memory: Any,
        stand_factory: Any | None = None,
        max_steps: int = 20,
    ) -> None:
        super().__init__()
        self._llm = llm
        self._tools = tool_registry
        self._memory = memory
        self._factory = stand_factory  # callable(StandType) -> Stand
        self._max_steps = max_steps

    async def execute(self, task: str, context: dict[str, Any] | None = None) -> StandResult:
        """Orchestrator ReAct loop — can summon sub-agent Stands."""
        from jojo.core.context_manager import ContextManager

        self._status = StandStatus.ACTIVE
        ctx = context or {}
        max_steps = ctx.get("max_steps", self._max_steps)

        tool_desc = self._tools.get_tool_descriptions()
        memory_text = _format_memories(self._memory, task)

        system_prompt = (
            "You are GOLD EXPERIENCE（ゴールド・エクスペリエンス）.\n"
            "Ability: Life Giver — spawn sub-agent Stands for complex tasks.\n\n"
            "When a task is complex, break it down and summon Stands:\n"
            f"{_describe_spawnable()}\n\n"
            "After spawning, synthesise their results into a final answer.\n"
            "「このジョルノ・ジョバァーナには夢がある！」\n\n"
            f"## Available Tools\n{tool_desc}"
            f"{memory_text}"
        )

        ctx_mgr = ContextManager(max_tokens=ctx.get("max_history_tokens", 8000))
        ctx_mgr.add_message({"role": "system", "content": system_prompt})
        ctx_mgr.add_message({"role": "user", "content": task})

        tool_records: list[dict[str, Any]] = []
        stands_used: list[str] = []

        try:
            for step in range(max_steps):
                response = self._llm.invoke(ctx_mgr.get_messages())
                tool_calls = _extract_tool_calls(response)

                if not tool_calls:
                    answer = _extract_text(response)
                    ctx_mgr.add_message({"role": "assistant", "content": answer})
                    return self._succeed(
                        answer,
                        steps=step + 1,
                        tool_calls=tool_records,
                        stands_used=stands_used,
                    )

                ctx_mgr.add_message({
                    "role": "assistant",
                    "content": _extract_text(response),
                    "tool_calls": tool_calls,
                })

                for tc in tool_calls:
                    if tc["name"] == "summon_stand":
                        result_text = await self._handle_summon(tc.get("arguments", {}), ctx)
                        stands_used.append(tc.get("arguments", {}).get("stand_name", "unknown"))
                    else:
                        result_text = await self._tools.call(tc["name"], tc.get("arguments", {}))

                    result_text = ContextManager.truncate_tool_result(str(result_text))
                    ctx_mgr.add_message({
                        "role": "tool",
                        "content": result_text,
                        "tool_call_id": tc.get("id", ""),
                    })
                    tool_records.append({
                        "name": tc["name"],
                        "arguments": tc.get("arguments", {}),
                        "result": result_text,
                    })

            return self._succeed(
                "Gold Experience: max steps reached. 無駄無駄…",
                steps=max_steps,
                tool_calls=tool_records,
                stands_used=stands_used,
            )
        except Exception as exc:
            logger.exception("Gold Experience failed — task_id=%s", self._task_id)
            return self._fail(str(exc))

    async def _handle_summon(self, args: dict[str, Any], ctx: dict[str, Any]) -> str:
        """Summon a sub-agent Stand and execute its task."""
        stand_name = args.get("stand_name", args.get("name", ""))
        sub_task = args.get("task", "")

        if not self._factory:
            return "[GOLD EXPERIENCE] No stand factory available."

        try:
            stand_type = _resolve_stand_type(stand_name)
            if stand_type not in SPAWNABLE_TYPES:
                return f"[GOLD EXPERIENCE] Cannot spawn {stand_name} — not a spawnable Stand."

            stand = self._factory(stand_type)
            result = await stand.execute(sub_task, ctx)

            if result.status == StandStatus.RETIRED:
                return f"[{result.stand_type.value}] Completed.\n{result.output}"
            return f"[{result.stand_type.value}] Failed: {result.error}"
        except Exception as exc:
            return f"[GOLD EXPERIENCE] Summon failed: {exc}"


def _resolve_stand_type(name: str) -> StandType:
    """Resolve a stand name string to StandType."""
    name_lower = name.lower().strip()
    try:
        return StandType(name_lower)
    except ValueError:
        pass
    for st in SPAWNABLE_TYPES:
        p = STAND_PROFILES[st]
        if name_lower in p.name.lower() or name_lower in st.name.lower():
            return st
    raise ValueError(f"Unknown Stand: '{name}'. Spawnable: {[st.value for st in SPAWNABLE_TYPES]}")


def _describe_spawnable() -> str:
    lines = []
    for st in SPAWNABLE_TYPES:
        p = STAND_PROFILES[st]
        lines.append(f"- `summon_stand(\"{st.value}\")` — {p.name}: {p.ability_description}")
    return "\n".join(lines)


def _format_memories(memory: Any, query: str) -> str:
    if memory is None:
        return ""
    try:
        hits = memory.recall(query, top_k=5)
        if not hits:
            return ""
        lines = [f"- [{h.match_type}] {h.content}" for h in hits]
        return "\n\n## Relevant Memories\n" + "\n".join(lines)
    except Exception:
        return ""


def _extract_tool_calls(response: Any) -> list[dict[str, Any]]:
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
    return str(response.content) if hasattr(response, "content") else str(response)
