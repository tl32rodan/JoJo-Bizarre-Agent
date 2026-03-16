"""CRAZY DIAMOND（クレイジー・ダイヤモンド）— Restoration Stand.

Error recovery and self-healing pipeline (in-process).
Pipeline: detect error → diagnose root cause → attempt fix → verify.

CRAZY DIAMOND inspects recent agent/tool failures, analyses logs or
error messages, and proposes (or directly applies) corrective actions
such as retrying with adjusted parameters, rolling back state, or
restarting a failed Stand.
"""

from __future__ import annotations

import logging
from typing import Any

from stand_master.stands.base import Stand, StandResult, StandStatus, StandType

logger = logging.getLogger(__name__)


class CrazyDiamond(Stand):
    """「直す（なおす）！」"""

    stand_type = StandType.CRAZY_DIAMOND

    def __init__(
        self,
        llm: Any = None,
        tool_registry: Any | None = None,
        memory_store: Any | None = None,
    ) -> None:
        super().__init__()
        self._llm = llm
        self._tools = tool_registry
        self._memory = memory_store

    async def execute(self, task: str, context: dict[str, Any] | None = None) -> StandResult:
        """Recovery pipeline: diagnose → plan fix → execute → verify."""
        self._status = StandStatus.ACTIVE
        logger.info("CRAZY DIAMOND activated — task_id=%s", self._task_id)

        ctx = context or {}
        error_info = ctx.get("error", task)
        failed_stand = ctx.get("failed_stand", "")
        recent_tool_calls = ctx.get("recent_tool_calls", [])

        if self._llm is None:
            return self._fail("CRAZY DIAMOND has no LLM for diagnosis.")

        try:
            # Step 1: Diagnose — ask LLM to analyse the error
            diagnosis_prompt = self._build_diagnosis_prompt(error_info, failed_stand, recent_tool_calls)
            messages: list[dict[str, Any]] = [
                {"role": "system", "content": (
                    "You are CRAZY DIAMOND（クレイジー・ダイヤモンド）, a Restoration Stand.\n"
                    "Your ability is to restore and fix anything.\n"
                    "Analyse the error, diagnose the root cause, and propose a concrete fix.\n"
                    "Output a JSON object with keys: diagnosis, root_cause, fix_action, fix_params."
                )},
                {"role": "user", "content": diagnosis_prompt},
            ]

            response = self._llm.invoke(messages)
            diagnosis_text = self._extract_text(response)

            # Step 2: Attempt fix — execute corrective action if tools available
            fix_result = None
            if self._tools is not None and ctx.get("auto_fix", False):
                fix_result = await self._attempt_auto_fix(diagnosis_text, ctx)

            # Step 3: Verify — store recovery record in memory
            if self._memory is not None:
                self._memory.store(
                    f"[CRAZY DIAMOND recovery] Error: {str(error_info)[:200]} | "
                    f"Diagnosis: {diagnosis_text[:200]}",
                    {"type": "recovery", "stand": failed_stand},
                )

            return self._succeed(
                {
                    "diagnosis": diagnosis_text,
                    "fix_applied": fix_result is not None,
                    "fix_result": fix_result,
                },
                failed_stand=failed_stand,
            )

        except Exception as exc:
            logger.exception("CRAZY DIAMOND failed — task_id=%s", self._task_id)
            return self._fail(str(exc))

    def _build_diagnosis_prompt(
        self,
        error_info: str,
        failed_stand: str,
        recent_tool_calls: list[dict[str, Any]],
    ) -> str:
        parts = [f"## Error\n{error_info}"]
        if failed_stand:
            parts.append(f"\n## Failed Stand\n{failed_stand}")
        if recent_tool_calls:
            tool_summary = "\n".join(
                f"- {tc.get('name', '?')}: {str(tc.get('result', ''))[:200]}"
                for tc in recent_tool_calls[-5:]
            )
            parts.append(f"\n## Recent Tool Calls\n{tool_summary}")
        parts.append("\nDiagnose the root cause and propose a fix.")
        return "\n".join(parts)

    async def _attempt_auto_fix(self, diagnosis: str, ctx: dict[str, Any]) -> str | None:
        """Try to execute a corrective tool call based on diagnosis."""
        retry_tool = ctx.get("retry_tool")
        retry_args = ctx.get("retry_args", {})
        if retry_tool:
            result = await self._tools.call(retry_tool, retry_args)
            return str(result)
        return None

    @staticmethod
    def _extract_text(response: Any) -> str:
        if hasattr(response, "content"):
            return str(response.content)
        return str(response)
