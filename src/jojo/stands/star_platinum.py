"""STAR PLATINUM（スタープラチナ）— Precision + Time Stop.

Ability: Precision — direct, general-purpose ReAct execution.
         Time Stop — deep chain-of-thought reasoning (optional reasoning model).

Star Platinum is the default Stand. It uses the standard LLM for regular
tasks, but can activate "The World" (Time Stop) mode to switch to a
dedicated reasoning model for deeper analysis.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from jojo.stands.base import Stand, StandResult, StandStatus, StandType

logger = logging.getLogger(__name__)


class StarPlatinum(Stand):
    """「オラオラオラ！」…「スタープラチナ ザ・ワールド！」"""

    stand_type = StandType.STAR_PLATINUM

    def __init__(
        self,
        llm: Any,
        tool_registry: Any,
        memory: Any,
        reasoning_llm: Any | None = None,
        permissions: Any | None = None,
        max_steps: int = 15,
    ) -> None:
        super().__init__()
        self._llm = llm
        self._reasoning_llm = reasoning_llm  # The World's power
        self._tools = tool_registry
        self._memory = memory
        self._permissions = permissions
        self._max_steps = max_steps

    async def execute(self, task: str, context: dict[str, Any] | None = None) -> StandResult:
        """ReAct loop with optional Time Stop (deep reasoning) mode.

        Pass context={"time_stop": True} to activate The World's power.
        """
        from jojo.core.context_manager import ContextManager

        self._status = StandStatus.ACTIVE
        ctx = context or {}
        time_stop = ctx.get("time_stop", False)
        max_steps = ctx.get("max_steps", self._max_steps)

        # Time Stop: use reasoning model + higher step budget
        if time_stop and self._reasoning_llm:
            llm = self._reasoning_llm
            max_steps = ctx.get("max_steps", 30)
            ability_text = (
                "Ability: Star Platinum — The World!\n"
                "Time Stop activated. Think deeply, step by step.\n"
                "Be thorough. Use all available tools to gather facts.\n"
                "「時よ止まれ！」"
            )
        else:
            llm = self._llm
            ability_text = (
                "Ability: Precision — direct, efficient execution.\n"
                "Use tools when needed. Be concise. Get results.\n"
                "「オラオラオラ！」"
            )

        tool_desc = self._tools.get_tool_descriptions()
        memory_text = _format_memories(self._memory, task)

        system_prompt = (
            f"You are STAR PLATINUM（スタープラチナ）.\n"
            f"{ability_text}\n\n"
            f"## Available Tools\n{tool_desc}"
            f"{memory_text}"
        )

        ctx_mgr = ContextManager(max_tokens=ctx.get("max_history_tokens", 8000))
        ctx_mgr.add_message({"role": "system", "content": system_prompt})
        ctx_mgr.add_message({"role": "user", "content": task})

        tool_records: list[dict[str, Any]] = []
        mode = "time_stop" if time_stop else "precision"

        try:
            for step in range(max_steps):
                response = llm.invoke(ctx_mgr.get_messages())
                tool_calls = _extract_tool_calls(response)

                if not tool_calls:
                    answer = _extract_text(response)
                    ctx_mgr.add_message({"role": "assistant", "content": answer})
                    return self._succeed(
                        answer, steps=step + 1, tool_calls=tool_records, mode=mode,
                    )

                ctx_mgr.add_message({
                    "role": "assistant",
                    "content": _extract_text(response),
                    "tool_calls": tool_calls,
                })

                for tc in tool_calls:
                    result = await self._tools.call(tc["name"], tc.get("arguments", {}))
                    result = ContextManager.truncate_tool_result(result)
                    ctx_mgr.add_message({
                        "role": "tool",
                        "content": result,
                        "tool_call_id": tc.get("id", ""),
                    })
                    tool_records.append({
                        "name": tc["name"],
                        "arguments": tc.get("arguments", {}),
                        "result": result,
                    })

            return self._succeed(
                "Star Platinum: max steps reached. やれやれだぜ…",
                steps=max_steps,
                tool_calls=tool_records,
                mode=mode,
            )
        except Exception as exc:
            logger.exception("Star Platinum failed — task_id=%s", self._task_id)
            return self._fail(str(exc))


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
