"""HIEROPHANT GREEN（法皇の緑）— The Researcher.

Ability 1: Emerald Splash — deep RAG research via SMAK + FAISS.
Ability 2: 20m Emerald Barrier — methodology enforcement via SKILL.md patterns.

Hierophant Green is long-range, methodical, and thorough.  It reaches
deep into codebases and knowledge bases.  Read-only — never modifies code.

「誰も『エメラルドスプラッシュ』をかわせない！」
"""

from __future__ import annotations

import json
import logging
from typing import Any

from jojo.stands.base import Stand, StandResult, StandStatus, StandType

logger = logging.getLogger(__name__)


class HierophantGreen(Stand):
    """「エメラルドスプラッシュ！」"""

    stand_type = StandType.HIEROPHANT_GREEN

    def __init__(
        self,
        memory_store: Any | None = None,
        query_service: Any | None = None,
        llm: Any | None = None,
        skills: list[Any] | None = None,
        tool_registry: Any | None = None,
        top_k: int = 10,
    ) -> None:
        super().__init__()
        self._memory = memory_store
        self._query_service = query_service
        self._llm = llm
        self._skills = skills or []
        self._tools = tool_registry
        self._top_k = top_k

    async def execute(self, task: str, context: dict[str, Any] | None = None) -> StandResult:
        """Route to Emerald Splash (RAG) or 20m Barrier (methodology)."""
        self._status = StandStatus.ACTIVE
        ctx = context or {}
        mode = ctx.get("mode", "splash")

        logger.info("HIEROPHANT GREEN activated — mode=%s, task_id=%s", mode, self._task_id)

        if mode == "barrier" and self._llm is not None:
            return await self._barrier_mode(task, ctx)
        return await self._splash_mode(task, ctx)

    # ------------------------------------------------------------------
    # Emerald Splash — RAG pipeline (enhanced from original)
    # ------------------------------------------------------------------

    async def _splash_mode(self, task: str, ctx: dict[str, Any]) -> StandResult:
        """Search pipeline: memory recall + SMAK query → consolidated results."""
        top_k = ctx.get("top_k", self._top_k)
        results: dict[str, Any] = {"memory_hits": [], "smak_hits": []}

        try:
            # Step 1: Vector memory recall
            if self._memory is not None:
                hits = self._memory.recall(task, top_k=top_k)
                results["memory_hits"] = [
                    {"content": h.content, "score": getattr(h, "score", None)}
                    for h in (hits or [])
                ]

            # Step 2: SMAK deep query with relation expansion
            if self._query_service is not None:
                index_name = ctx.get("index", None)
                smak_results = self._query_service.query(
                    task, top_k=top_k, index_name=index_name,
                )
                results["smak_hits"] = [
                    {
                        "uid": getattr(r, "uid", ""),
                        "content": getattr(r, "content", str(r)),
                        "source_type": getattr(r, "source_type", ""),
                        "relations": getattr(r, "relations", []),
                    }
                    for r in (smak_results or [])
                ]

            # Step 3: Consolidate
            total = len(results["memory_hits"]) + len(results["smak_hits"])
            if total == 0:
                return self._succeed(
                    "HIEROPHANT GREEN found no relevant information.", total_hits=0,
                )

            lines: list[str] = []
            for i, hit in enumerate(results["memory_hits"], 1):
                lines.append(f"[Memory #{i}] {hit['content']}")
            for i, hit in enumerate(results["smak_hits"], 1):
                lines.append(f"[SMAK #{i}] ({hit['source_type']}) {hit['content']}")

            return self._succeed(
                "\n---\n".join(lines), total_hits=total, raw=results,
            )

        except Exception as exc:
            logger.exception("Emerald Splash failed — task_id=%s", self._task_id)
            return self._fail(str(exc))

    # ------------------------------------------------------------------
    # 20m Emerald Barrier — LLM-guided methodology enforcement
    # ------------------------------------------------------------------

    async def _barrier_mode(self, task: str, ctx: dict[str, Any]) -> StandResult:
        """LLM-guided research using SKILL.md methodology patterns."""
        from jojo.core.context_manager import ContextManager

        try:
            # 1. Gather context via Emerald Splash first
            splash_result = await self._splash_mode(task, ctx)
            research_context = str(splash_result.output) if splash_result.output else ""

            # 2. Load applicable SKILL.md methodologies
            methodology = self._build_methodology_prompt(task)

            # 3. Build read-only tool descriptions
            tool_desc = ""
            if self._tools is not None:
                tool_desc = f"\n\n## Available Tools (READ-ONLY)\n{self._tools.get_tool_descriptions()}"

            system_prompt = (
                "You are HIEROPHANT GREEN（法皇の緑）.\n"
                "Ability: 20m Emerald Barrier — deep analysis using structured methodology.\n\n"
                "IMPORTANT: You are READ-ONLY. You may search, read, and analyse code,\n"
                "but you must NEVER modify files or run destructive commands.\n\n"
                "Your output must be a structured research report or methodology-guided plan.\n"
                "「結界だ… 逃がさん！」\n"
                f"{methodology}"
                f"\n\n## Research Context\n{research_context[:3000]}"
                f"{tool_desc}"
            )

            ctx_mgr = ContextManager(max_tokens=ctx.get("max_history_tokens", 8000))
            ctx_mgr.add_message({"role": "system", "content": system_prompt})
            ctx_mgr.add_message({"role": "user", "content": task})

            max_steps = ctx.get("max_steps", 15)
            tool_records: list[dict[str, Any]] = []

            for step in range(max_steps):
                response = self._llm.invoke(ctx_mgr.get_messages())
                tool_calls = _extract_tool_calls(response)

                if not tool_calls:
                    answer = _extract_text(response)
                    ctx_mgr.add_message({"role": "assistant", "content": answer})
                    return self._succeed(
                        answer, steps=step + 1, mode="barrier",
                        tool_calls=tool_records,
                    )

                ctx_mgr.add_message({
                    "role": "assistant",
                    "content": _extract_text(response),
                    "tool_calls": tool_calls,
                })

                for tc in tool_calls:
                    # Enforce read-only: block write/delete/exec tools
                    if _is_write_tool(tc["name"]):
                        result = f"[BARRIER] Tool '{tc['name']}' blocked — read-only mode."
                    elif self._tools is not None:
                        result = await self._tools.call(tc["name"], tc.get("arguments", {}))
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
                "HIEROPHANT GREEN: barrier analysis reached max steps.",
                steps=max_steps, mode="barrier", tool_calls=tool_records,
            )

        except Exception as exc:
            logger.exception("20m Barrier failed — task_id=%s", self._task_id)
            return self._fail(str(exc))

    def _build_methodology_prompt(self, task: str) -> str:
        """Select and format applicable SKILL.md methodologies."""
        if not self._skills:
            return ""

        lines = ["\n\n## Methodology (from SKILL.md)"]
        for skill in self._skills:
            name = getattr(skill, "name", "unknown")
            body = getattr(skill, "body", "")
            lines.append(f"\n### {name}\n{body[:1500]}")
        return "\n".join(lines)


# ------------------------------------------------------------------
# Read-only enforcement
# ------------------------------------------------------------------

_WRITE_TOOLS = frozenset({
    "write_file", "delete_file", "create_file", "move_file",
    "run_terminal_command", "execute_command", "run_command",
    "bash", "shell",
})


def _is_write_tool(name: str) -> bool:
    return name.lower() in _WRITE_TOOLS


# ------------------------------------------------------------------
# LLM response parsing (shared helpers)
# ------------------------------------------------------------------

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
