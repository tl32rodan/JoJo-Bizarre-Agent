"""STONE FREE（ストーン・フリー）— Part 6 · Jolyne Cujoh.

Stand: STONE FREE
Ability: String Decomposition — unravels body into string to stretch,
         connect, create barriers, and detect vibrations.

As a JoJo persona: unravel complexity — decompose problems into threads,
find connections between seemingly unrelated things, weave understanding
from disparate parts.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from jojo.jojo_stands.base import JoJoStand, JoJoStandType

logger = logging.getLogger(__name__)


class StoneFree(JoJoStand):
    """「やれやれだわ…」"""

    stand_type = JoJoStandType.STONE_FREE

    def __init__(self, llm: Any, tool_registry: Any, memory: Any, config: Any) -> None:
        self._llm = llm
        self._tools = tool_registry
        self._memory = memory
        self._config = config

    def build_system_prompt(self, tool_descriptions: str, stand_descriptions: str) -> str:
        p = self.profile
        return (
            f"You are JoJo, currently channelling {p.name}（{p.name_jp}）.\n"
            f"Stand User: {p.user} (Part {p.part})\n"
            f"Ability: {p.ability_name} — {p.ability_description}\n\n"
            f"Philosophy: {p.philosophy}\n\n"
            "Your approach to every task:\n"
            "1. UNRAVEL — Decompose the problem into individual threads.\n"
            "2. CONNECT — Find links and dependencies between threads.\n"
            "3. WEAVE — Synthesise threads into a coherent understanding.\n"
            "4. BARRIER — Identify boundaries and constraints.\n\n"
            "Think of information as strings you can pull apart, stretch,\n"
            "and reconnect in new configurations.\n\n"
            "「やれやれだわ…」\n\n"
            f"## Available Tools\n{tool_descriptions}"
        )

    async def run(self, user_input: str, context: dict[str, Any]) -> dict[str, Any]:
        """Decomposition ReAct loop — unravel, connect, weave."""
        from jojo.core.context_manager import ContextManager

        memories = self._memory.recall(user_input, top_k=5)
        memory_text = ""
        if memories:
            memory_text = "\n## Relevant Memories\n" + "\n".join(
                f"- [{m.match_type}] {m.content}" for m in memories
            )

        system_prompt = self.build_system_prompt(
            tool_descriptions=self._tools.get_tool_descriptions(),
            stand_descriptions="",
        ) + memory_text

        ctx_mgr = ContextManager(max_tokens=self._config.session.max_history_tokens)
        ctx_mgr.add_message({"role": "system", "content": system_prompt})
        ctx_mgr.add_message({"role": "user", "content": user_input})

        tool_records: list[dict[str, Any]] = []
        max_steps = context.get("max_steps", 15)

        for step in range(max_steps):
            response = self._llm.invoke(ctx_mgr.get_messages())
            tool_calls = _extract_tool_calls(response)

            if not tool_calls:
                answer = _extract_text(response)
                ctx_mgr.add_message({"role": "assistant", "content": answer})
                return {"answer": answer, "steps": step + 1, "tool_calls": tool_records}

            ctx_mgr.add_message({
                "role": "assistant", "content": _extract_text(response), "tool_calls": tool_calls,
            })

            for tc in tool_calls:
                result = await self._tools.call(tc["name"], tc.get("arguments", {}))
                result = ContextManager.truncate_tool_result(result)
                ctx_mgr.add_message({"role": "tool", "content": result, "tool_call_id": tc.get("id", "")})
                tool_records.append({"name": tc["name"], "arguments": tc.get("arguments", {}), "result": result})

        return {
            "answer": "Stone Free: max steps reached. やれやれだわ…",
            "steps": max_steps,
            "tool_calls": tool_records,
        }


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
    return str(response.content) if hasattr(response, "content") else str(response)
