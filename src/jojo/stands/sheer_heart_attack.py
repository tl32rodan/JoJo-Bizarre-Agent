"""SHEER HEART ATTACK（シアーハートアタック）— Background Worker.

Ability: Automatic Tracking — fire-and-forget tasks via SubAgentBackend.

Spawned by Gold Experience.  Automatic, relentless, independent.
Uses OpenCode or tmux backend through the SubAgentBackend protocol.

「コッチヲ見ロ」
"""

from __future__ import annotations

import logging
from typing import Any

from jojo.services.backend import SubAgentBackend, TaskStatus
from jojo.stands.base import Stand, StandResult, StandStatus, StandType

logger = logging.getLogger(__name__)


class SheerHeartAttack(Stand):
    """「コッチヲ見ロ」"""

    stand_type = StandType.SHEER_HEART_ATTACK

    def __init__(
        self,
        backend: SubAgentBackend | None = None,
        timeout: float = 600.0,
    ) -> None:
        super().__init__()
        self._backend = backend
        self._timeout = timeout

    async def execute(self, task: str, context: dict[str, Any] | None = None) -> StandResult:
        """Background pipeline: spawn → (optionally) poll → collect."""
        self._status = StandStatus.ACTIVE
        logger.info("SHEER HEART ATTACK activated — task_id=%s", self._task_id)

        ctx = context or {}
        fire_and_forget: bool = ctx.get("fire_and_forget", True)
        agent: str = ctx.get("agent", "build")

        if self._backend is None:
            return self._fail("SHEER HEART ATTACK has no SubAgentBackend.")

        try:
            handle_id = await self._backend.spawn(
                task, agent=agent, context=ctx,
            )
            logger.info("SHEER HEART ATTACK spawned — handle=%s", handle_id)

            if fire_and_forget:
                return self._succeed(
                    f"Background task launched: {handle_id}",
                    handle_id=handle_id, mode="fire_and_forget",
                )

            # Blocking mode — wait for result.
            result = await self._backend.collect(handle_id, timeout=self._timeout)

            if result.status == TaskStatus.COMPLETED:
                return self._succeed(
                    result.output,
                    handle_id=handle_id,
                    mode="blocking",
                )
            return self._fail(
                result.error or "Task failed",
                handle_id=handle_id,
            )

        except Exception as exc:
            logger.exception("SHEER HEART ATTACK failed — task_id=%s", self._task_id)
            return self._fail(str(exc))
