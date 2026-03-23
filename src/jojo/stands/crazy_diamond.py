"""CRAZY DIAMOND（クレイジー・ダイヤモンド）— The Reviewer.

Ability 1: Restoration — code review, bug detection, fix suggestions.
Ability 2: Breakdown — verify output against requirements, check edge cases.

Josuke's Stand.  Fixes what's broken, restores to correct state.
Obsessed with quality.  Touch his hair and he'll destroy you.

「直す」
"""

from __future__ import annotations

import json
import logging
from typing import Any

from jojo.stands.base import Stand, StandResult, StandStatus, StandType

logger = logging.getLogger(__name__)


class CrazyDiamond(Stand):
    """「おい… 今おれの このヘアースタイルが カッコ悪いって言ったのか？」"""

    stand_type = StandType.CRAZY_DIAMOND

    def __init__(
        self,
        llm: Any,
        tool_registry: Any | None = None,
        memory: Any | None = None,
        skills: list[Any] | None = None,
        max_steps: int = 15,
    ) -> None:
        super().__init__()
        self._llm = llm
        self._tools = tool_registry
        self._memory = memory
        self._skills = skills or []
        self._max_steps = max_steps

    async def execute(self, task: str, context: dict[str, Any] | None = None) -> StandResult:
        """Route to Restoration (review) or Breakdown (verify)."""
        from jojo.core.context_manager import ContextManager

        self._status = StandStatus.ACTIVE
        ctx = context or {}
        mode = ctx.get("mode", "restoration")
        max_steps = ctx.get("max_steps", self._max_steps)

        logger.info("CRAZY DIAMOND activated — mode=%s, task_id=%s", mode, self._task_id)

        # Build mode-specific system prompt
        if mode == "breakdown":
            ability_text = self._breakdown_prompt(ctx)
        else:
            ability_text = self._restoration_prompt()

        tool_desc = ""
        if self._tools is not None:
            tool_desc = f"\n\n## Available Tools\n{self._tools.get_tool_descriptions()}"

        checklist = self._build_review_checklist()
        memory_text = _format_memories(self._memory, task)

        system_prompt = (
            "You are CRAZY DIAMOND（クレイジー・ダイヤモンド）.\n"
            f"{ability_text}\n\n"
            "IMPORTANT: You are a REVIEWER. You can read code, run tests, and "
            "run linters to detect issues. Report your findings clearly.\n"
            "Do NOT write or modify files unless explicitly told to fix.\n"
            "「直してやるよ」\n"
            f"{checklist}"
            f"{tool_desc}"
            f"{memory_text}"
        )

        ctx_mgr = ContextManager(max_tokens=ctx.get("max_history_tokens", 8000))
        ctx_mgr.add_message({"role": "system", "content": system_prompt})
        ctx_mgr.add_message({"role": "user", "content": task})

        tool_records: list[dict[str, Any]] = []

        try:
            for step in range(max_steps):
                response = self._llm.invoke(ctx_mgr.get_messages())
                tool_calls = _extract_tool_calls(response)

                if not tool_calls:
                    answer = _extract_text(response)
                    ctx_mgr.add_message({"role": "assistant", "content": answer})
                    return self._succeed(
                        answer, steps=step + 1, mode=mode, tool_calls=tool_records,
                    )

                ctx_mgr.add_message({
                    "role": "assistant",
                    "content": _extract_text(response),
                    "tool_calls": tool_calls,
                })

                for tc in tool_calls:
                    if self._tools is not None:
                        result = await self._tools.call(
                            tc["name"], tc.get("arguments", {}),
                        )
                    else:
                        result = f"[Tool '{tc['name']}' unavailable]"

                    result = ContextManager.truncate_tool_result(str(result))
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
                "CRAZY DIAMOND: max review steps reached.",
                steps=max_steps, mode=mode, tool_calls=tool_records,
            )
        except Exception as exc:
            logger.exception("CRAZY DIAMOND failed — task_id=%s", self._task_id)
            return self._fail(str(exc))

    # ------------------------------------------------------------------
    # Mode-specific prompts
    # ------------------------------------------------------------------

    def _restoration_prompt(self) -> str:
        return (
            "Ability: Restoration — code review mode.\n"
            "1. Read the code / diff carefully.\n"
            "2. Run tests and linters if available.\n"
            "3. Identify: bugs, security issues, style violations, logic errors.\n"
            "4. For each issue: describe it, explain the impact, suggest a fix.\n"
            "5. Summarise with a PASS / NEEDS_FIX verdict."
        )

    def _breakdown_prompt(self, ctx: dict[str, Any]) -> str:
        requirements = ctx.get("requirements", "")
        req_text = f"\n\n## Requirements to verify:\n{requirements}" if requirements else ""
        return (
            "Ability: Breakdown — output verification mode.\n"
            "You are given output from another Stand. Verify it:\n"
            "1. Does it meet the requirements?\n"
            "2. Are there edge cases not handled?\n"
            "3. Is the solution correct and complete?\n"
            "4. Summarise with a PASS / NEEDS_FIX verdict and specific issues."
            f"{req_text}"
        )

    def _build_review_checklist(self) -> str:
        """Build review checklist from loaded SKILL.md patterns."""
        if not self._skills:
            return ""
        lines = ["\n\n## Review Checklist (from SKILL.md)"]
        for skill in self._skills:
            name = getattr(skill, "name", "unknown")
            hints = getattr(skill, "tool_hints", {})
            body = getattr(skill, "body", "")
            lines.append(f"\n### {name}")
            if hints:
                for tool, hint in hints.items():
                    lines.append(f"- [{tool}] {hint}")
            elif body:
                lines.append(body[:800])
        return "\n".join(lines)


# ------------------------------------------------------------------
# LLM response parsing
# ------------------------------------------------------------------

def _format_memories(memory: Any, query: str) -> str:
    if memory is None:
        return ""
    try:
        hits = memory.recall(query, top_k=3)
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
