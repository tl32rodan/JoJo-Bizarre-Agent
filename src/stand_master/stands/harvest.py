"""HARVEST（ハーヴェスト）— Colony Stand.

Parallel execution pipeline (in-process).
Accepts sub-tasks and executes them concurrently via asyncio.gather.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Awaitable

from stand_master.stands.base import Stand, StandResult, StandStatus, StandType

logger = logging.getLogger(__name__)

WorkerFn = Callable[[str, dict[str, Any]], Awaitable[Any]]


class Harvest(Stand):
    """「ハーヴェスト！」"""

    stand_type = StandType.HARVEST

    def __init__(self, worker: WorkerFn | None = None, max_concurrency: int = 10) -> None:
        super().__init__()
        self._worker = worker
        self._max_concurrency = max_concurrency

    async def execute(self, task: str, context: dict[str, Any] | None = None) -> StandResult:
        """Parallel pipeline: split → concurrent execute → collect."""
        self._status = StandStatus.ACTIVE
        logger.info("HARVEST activated — task_id=%s", self._task_id)

        ctx = context or {}
        sub_tasks: list[str] = ctx.get("sub_tasks", [task])

        if self._worker is None:
            return self._fail("HARVEST has no worker function assigned.")

        semaphore = asyncio.Semaphore(self._max_concurrency)

        async def _unit(idx: int, sub_task: str) -> dict[str, Any]:
            async with semaphore:
                try:
                    result = await self._worker(sub_task, ctx)
                    return {"index": idx, "task": sub_task, "status": "ok", "result": result}
                except Exception as exc:
                    logger.warning("HARVEST unit #%d failed: %s", idx, exc)
                    return {"index": idx, "task": sub_task, "status": "error", "error": str(exc)}

        try:
            unit_results = await asyncio.gather(*[_unit(i, t) for i, t in enumerate(sub_tasks)])
            succeeded = sum(1 for r in unit_results if r["status"] == "ok")
            failed = len(unit_results) - succeeded

            return self._succeed(unit_results, total=len(sub_tasks), succeeded=succeeded, failed=failed)

        except Exception as exc:
            logger.exception("HARVEST failed — task_id=%s", self._task_id)
            return self._fail(str(exc))
