"""THE WORLD（ザ・ワールド）— Close-Range Power Stand.

Deep, multi-step chain-of-thought reasoning.  Invokes a dedicated
reasoning model (potentially heavier) and runs an inner ReAct loop with
higher step budget so STAR PLATINUM can delegate hard problems.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from react_agent.stands.base import Stand, StandResult, StandStatus, StandType

logger = logging.getLogger(__name__)


class TheWorld(Stand):
    """「時よ止まれ！」— Stops time to think deeply."""

    stand_type = StandType.THE_WORLD

    def __init__(
        self,
        llm: Any,
        tool_registry: Any | None = None,
        max_steps: int = 30,
    ) -> None:
        super().__init__()
        self._llm = llm
        self._tools = tool_registry
        self._max_steps = max_steps

    async def execute(self, task: str, context: dict[str, Any] | None = None) -> StandResult:
        """Run deep ReAct reasoning on *task*.

        Uses a dedicated inner loop with a higher step budget and an
        optional reasoning-specialised model.
        """
        self._status = StandStatus.ACTIVE
        logger.info("THE WORLD activated — task_id=%s", self._task_id)

        ctx = context or {}
        system_prompt = (
            "You are THE WORLD（ザ・ワールド）, a close-range power Stand.\n"
            "Your ability is deep chain-of-thought reasoning.\n"
            "Think step by step. Be thorough and precise.\n"
            "Use tools when available to gather facts before concluding.\n"
        )

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
        ]

        # Inject prior context if provided.
        if ctx.get("history"):
            messages.append({
                "role": "system",
                "content": f"Prior conversation context:\n{ctx['history']}",
            })

        messages.append({"role": "user", "content": task})

        try:
            tool_calls_log: list[dict[str, Any]] = []

            for step in range(self._max_steps):
                response = self._llm.invoke(messages)

                # Extract tool calls.
                raw_tool_calls = self._extract_tool_calls(response)

                if not raw_tool_calls:
                    # Final answer reached.
                    answer = self._extract_text(response)
                    return self._succeed(
                        answer,
                        steps=step + 1,
                        tool_calls=tool_calls_log,
                    )

                # Record assistant message with tool_calls.
                messages.append({
                    "role": "assistant",
                    "content": self._extract_text(response),
                    "tool_calls": raw_tool_calls,
                })

                for tc in raw_tool_calls:
                    tool_name = tc["name"]
                    tool_args = tc.get("arguments", {})

                    if self._tools is not None:
                        result = await self._tools.call(tool_name, tool_args)
                    else:
                        result = f"[Tool '{tool_name}' unavailable in THE WORLD]"

                    messages.append({
                        "role": "tool",
                        "content": str(result)[:4000],
                        "tool_call_id": tc.get("id", ""),
                    })
                    tool_calls_log.append({
                        "name": tool_name,
                        "arguments": tool_args,
                        "result": str(result)[:500],
                    })

            return self._succeed(
                "THE WORLD: maximum reasoning steps reached.",
                steps=self._max_steps,
                tool_calls=tool_calls_log,
            )

        except Exception as exc:
            logger.exception("THE WORLD failed — task_id=%s", self._task_id)
            return self._fail(str(exc))

    # -- helpers (mirrors agent_loop helpers) --

    @staticmethod
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

    @staticmethod
    def _extract_text(response: Any) -> str:
        if hasattr(response, "content"):
            return str(response.content)
        return str(response)
