"""SHEER HEART ATTACK（シアーハートアタック）— Automatic Stand.

Background task pipeline (spawned as subagent via GOLD EXPERIENCE).
Launches a task via SubAgentSpawner (tmux/cron) and optionally polls.

When the task is "fire_and_forget" (default), STAR PLATINUM gets an
immediate acknowledgement. The actual work runs in a separate process
via stands/runner.py.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from stand_master.stands.base import Stand, StandResult, StandStatus, StandType

logger = logging.getLogger(__name__)


class SheerHeartAttack(Stand):
    """「コッチヲ見ロ」"""

    stand_type = StandType.SHEER_HEART_ATTACK

    def __init__(
        self,
        spawner: Any | None = None,
        poll_interval: float = 5.0,
        timeout: float = 600.0,
    ) -> None:
        super().__init__()
        self._spawner = spawner
        self._poll_interval = poll_interval
        self._timeout = timeout

    async def execute(self, task: str, context: dict[str, Any] | None = None) -> StandResult:
        """Background pipeline: spawn → (optionally) poll → collect."""
        self._status = StandStatus.ACTIVE
        logger.info("SHEER HEART ATTACK activated — task_id=%s", self._task_id)

        ctx = context or {}
        fire_and_forget: bool = ctx.get("fire_and_forget", True)

        if self._spawner is None:
            return self._fail("SHEER HEART ATTACK has no SubAgentSpawner.")

        try:
            handle = self._spawner.spawn(task, context=ctx)
            logger.info("SHEER HEART ATTACK spawned sub-agent %s", handle.task_id)

            if fire_and_forget:
                return self._succeed(
                    f"Background task launched: {handle.task_id}",
                    sub_task_id=handle.task_id, mode="fire_and_forget",
                )

            # Poll until done.
            elapsed = 0.0
            while elapsed < self._timeout:
                await asyncio.sleep(self._poll_interval)
                elapsed += self._poll_interval
                sub_result = self._spawner.collect(handle)
                if sub_result.status.value in ("completed", "failed"):
                    return self._succeed(
                        sub_result.output or sub_result.error,
                        sub_task_id=handle.task_id,
                        sub_status=sub_result.status.value,
                        elapsed=elapsed,
                    )

            return self._fail(f"Timed out after {self._timeout}s", sub_task_id=handle.task_id)

        except Exception as exc:
            logger.exception("SHEER HEART ATTACK failed — task_id=%s", self._task_id)
            return self._fail(str(exc))
