"""GOLD EXPERIENCE（ゴールド・エクスペリエンス）— Part 5 · Giorno Giovanna.

Stand: GOLD EXPERIENCE
Ability: Life Giver — bestows life upon objects, creating living organisms.

As a JoJo persona: the orchestrator who spawns and manages sub-agents.
Gold Experience is the ONLY JoJo Stand that can summon non-JoJo stands
(THE WORLD, HIEROPHANT GREEN, HARVEST, SHEER HEART ATTACK) as sub-agents.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from jojo.jojo_stands.base import JoJoStand, JoJoStandType

logger = logging.getLogger(__name__)


class GoldExperience(JoJoStand):
    """「無駄無駄無駄！」"""

    stand_type = JoJoStandType.GOLD_EXPERIENCE

    def __init__(self, llm: Any, tool_registry: Any, memory: Any, config: Any) -> None:
        self._llm = llm
        self._tools = tool_registry
        self._memory = memory
        self._config = config
        # Stand spawner injected separately — holds refs to spawnable stand factory
        self._stand_spawner: Any = None

    def set_stand_spawner(self, spawner: Any) -> None:
        """Inject the spawnable-stand factory (stands.arrow.GoldExperience)."""
        self._stand_spawner = spawner

    def build_system_prompt(self, tool_descriptions: str, stand_descriptions: str) -> str:
        p = self.profile
        return (
            f"You are JoJo, currently channelling {p.name}（{p.name_jp}）.\n"
            f"Stand User: {p.user} (Part {p.part})\n"
            f"Ability: {p.ability_name} — {p.ability_description}\n\n"
            f"Philosophy: {p.philosophy}\n\n"
            "You are the orchestrator. Your unique power is to GIVE LIFE — \n"
            "spawn specialised sub-agent Stands to handle parts of a task.\n\n"
            "When a task is complex, break it into sub-tasks and summon Stands:\n"
            "- `summon_stand(\"the_world\")` — deep reasoning\n"
            "- `summon_stand(\"hierophant_green\")` — semantic search / RAG\n"
            "- `summon_stand(\"harvest\")` — parallel batch operations\n"
            "- `summon_stand(\"sheer_heart_attack\")` — background jobs\n\n"
            "After spawning, monitor their progress and synthesise results.\n"
            "「このジョルノ・ジョバァーナには夢がある！」\n\n"
            f"## Spawnable Stands\n{stand_descriptions}\n\n"
            f"## Available Tools\n{tool_descriptions}"
        )

    async def run(self, user_input: str, context: dict[str, Any]) -> dict[str, Any]:
        """Orchestrator ReAct loop — can spawn sub-agent stands."""
        from jojo.core.context_manager import ContextManager

        memories = self._memory.recall(user_input, top_k=5)
        memory_text = ""
        if memories:
            memory_text = "\n## Relevant Memories\n" + "\n".join(
                f"- [{m.match_type}] {m.content}" for m in memories
            )

        stand_descriptions = ""
        if self._stand_spawner and hasattr(self._stand_spawner, "describe_stands"):
            stand_descriptions = self._stand_spawner.describe_stands()

        system_prompt = self.build_system_prompt(
            tool_descriptions=self._tools.get_tool_descriptions(),
            stand_descriptions=stand_descriptions,
        ) + memory_text

        ctx_mgr = ContextManager(max_tokens=self._config.session.max_history_tokens)
        ctx_mgr.add_message({"role": "system", "content": system_prompt})
        ctx_mgr.add_message({"role": "user", "content": user_input})

        tool_records: list[dict[str, Any]] = []
        stand_results: list[dict[str, Any]] = []
        max_steps = context.get("max_steps", 20)

        for step in range(max_steps):
            response = self._llm.invoke(ctx_mgr.get_messages())
            tool_calls = _extract_tool_calls(response)

            if not tool_calls:
                answer = _extract_text(response)
                ctx_mgr.add_message({"role": "assistant", "content": answer})
                return {
                    "answer": answer,
                    "steps": step + 1,
                    "tool_calls": tool_records,
                    "stands_summoned": stand_results,
                }

            ctx_mgr.add_message({
                "role": "assistant", "content": _extract_text(response), "tool_calls": tool_calls,
            })

            for tc in tool_calls:
                if tc["name"] == "summon_stand":
                    result = await self._handle_summon(tc.get("arguments", {}), context)
                    stand_results.append(result)
                    result_text = json.dumps(result, ensure_ascii=False, default=str)
                else:
                    result_text = await self._tools.call(tc["name"], tc.get("arguments", {}))

                result_text = ContextManager.truncate_tool_result(result_text)
                ctx_mgr.add_message({"role": "tool", "content": result_text, "tool_call_id": tc.get("id", "")})
                tool_records.append({"name": tc["name"], "arguments": tc.get("arguments", {}), "result": result_text})

        return {
            "answer": "Gold Experience: max steps reached. 無駄無駄…",
            "steps": max_steps,
            "tool_calls": tool_records,
            "stands_summoned": stand_results,
        }

    async def _handle_summon(self, arguments: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Summon a non-JoJo stand and execute its task."""
        stand_name = arguments.get("stand_name", arguments.get("name", ""))
        task = arguments.get("task", "")

        if not self._stand_spawner:
            return {"error": "No stand spawner available", "stand": stand_name}

        try:
            stand = self._stand_spawner.summon_by_name(stand_name)
            result = await stand.execute(task, context)
            return {
                "stand": stand_name,
                "status": "completed",
                "result": result.output if hasattr(result, "output") else str(result),
            }
        except Exception as exc:
            logger.exception("Failed to summon %s", stand_name)
            return {"stand": stand_name, "status": "failed", "error": str(exc)}

    @staticmethod
    def describe_spawnable_stands() -> str:
        """Describe the non-JoJo stands that Gold Experience can spawn."""
        return (
            "| Stand | Ability | Mode |\n"
            "|---|---|---|\n"
            "| THE WORLD | Close-Range Power (deep reasoning) | in-process |\n"
            "| HIEROPHANT GREEN | Long-Range RAG (semantic search) | subagent |\n"
            "| HARVEST | Colony (parallel batch) | in-process |\n"
            "| SHEER HEART ATTACK | Automatic (background jobs) | subagent |\n"
        )


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
