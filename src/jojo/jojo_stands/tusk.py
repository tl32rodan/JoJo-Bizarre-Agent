"""TUSK（タスク）— Part 7 · Johnny Joestar.

Stand: TUSK
Ability: Infinite Rotation — evolves through Acts 1–4.
  Act 1: basic shots (broad search)
  Act 2: guided shots (refined search)
  Act 3: self-guiding (deep analysis)
  Act 4: infinite rotation — unstoppable, transcends dimensions.

As a JoJo persona: iterative deepening — start with a broad, simple pass,
then progressively drill deeper with each Act.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from jojo.jojo_stands.base import JoJoStand, JoJoStandType

logger = logging.getLogger(__name__)


class Tusk(JoJoStand):
    """「納得」はすべてに優先するぜッ！！"""

    stand_type = JoJoStandType.TUSK

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
            "You work in ACTS — each act drills deeper:\n\n"
            "**Act 1 — Nail Shot** (Broad scan)\n"
            "  Cast a wide net. Gather surface-level information.\n\n"
            "**Act 2 — Guided Shot** (Focused search)\n"
            "  Based on Act 1 findings, narrow focus. Pursue leads.\n\n"
            "**Act 3 — Self-Guiding** (Deep analysis)\n"
            "  Synthesise findings. Draw connections. Build understanding.\n\n"
            "**Act 4 — Infinite Rotation** (Unstoppable conclusion)\n"
            "  Deliver the final answer with full confidence and depth.\n"
            "  Once Act 4 spins, nothing can deflect it.\n\n"
            "Always state which Act you are currently in.\n\n"
            f"## Available Tools\n{tool_descriptions}"
        )

    async def run(self, user_input: str, context: dict[str, Any]) -> dict[str, Any]:
        """Iterative deepening ReAct loop — Act 1 → Act 4."""
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
        ctx_mgr.add_message({
            "role": "user",
            "content": (
                f"{user_input}\n\n"
                "Begin with Act 1 (broad scan), then progress through Acts 2–4."
            ),
        })

        tool_records: list[dict[str, Any]] = []
        # Tusk gets a higher step budget for its multi-act approach
        max_steps = context.get("max_steps", 25)

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
            "answer": "Tusk Act 4: max steps reached. The rotation continues…",
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
