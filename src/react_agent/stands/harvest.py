"""HARVEST（ハーヴェスト）— Colony Stand.

Splits into many small units that work in parallel.
Accepts a list of sub-tasks and executes them concurrently using
``asyncio.gather``, collecting results from each unit.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Awaitable

from react_agent.stands.base import Stand, StandResult, StandStatus, StandType

logger = logging.getLogger(__name__)

# Type alias for a worker callable: (task_str, context) -> result
WorkerFn = Callable[[str, dict[str, Any]], Awaitable[Any]]


class Harvest(Stand):
    """「ハーヴェスト！」— 500 units, all at once."""

    stand_type = StandType.HARVEST

    def __init__(
        self,
        worker: WorkerFn | None = None,
        max_concurrency: int = 10,
    ) -> None:
        super().__init__()
        self._worker = worker
        self._max_concurrency = max_concurrency

    async def execute(self, task: str, context: dict[str, Any] | None = None) -> StandResult:
        """Run sub-tasks in parallel.

        Expects ``context["sub_tasks"]`` to be a list of task strings.
        Each is dispatched to the worker function concurrently, bounded
        by a semaphore of *max_concurrency*.
        """
        self._status = StandStatus.ACTIVE
        logger.info("HARVEST activated — task_id=%s", self._task_id)

        ctx = context or {}
        sub_tasks: list[str] = ctx.get("sub_tasks", [])

        if not sub_tasks:
            # If no explicit sub_tasks, treat the main task as a single item.
            sub_tasks = [task]

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
            unit_results = await asyncio.gather(
                *[_unit(i, t) for i, t in enumerate(sub_tasks)]
            )

            succeeded = sum(1 for r in unit_results if r["status"] == "ok")
            failed = sum(1 for r in unit_results if r["status"] == "error")

            logger.info(
                "HARVEST completed — %d/%d succeeded", succeeded, len(sub_tasks)
            )
            return self._succeed(
                unit_results,
                total=len(sub_tasks),
                succeeded=succeeded,
                failed=failed,
            )

        except Exception as exc:
            logger.exception("HARVEST failed — task_id=%s", self._task_id)
            return self._fail(str(exc))
