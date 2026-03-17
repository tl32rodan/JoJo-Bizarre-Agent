"""HIEROPHANT GREEN（法皇の緑）— Long-Range Stand.

Search & retrieval pipeline (spawned as subagent via GOLD EXPERIENCE).
Pipeline: embed query → vector search → SMAK relation expansion → consolidate.

When run as a subagent process (via stands/runner.py), this Stand
operates independently with its own memory and embedding stack.
"""

from __future__ import annotations

import logging
from typing import Any

from stand_master.stands.base import Stand, StandResult, StandStatus, StandType

logger = logging.getLogger(__name__)


class HierophantGreen(Stand):
    """「エメラルドスプラッシュ！」"""

    stand_type = StandType.HIEROPHANT_GREEN

    def __init__(
        self,
        memory_store: Any | None = None,
        query_service: Any | None = None,
        top_k: int = 10,
    ) -> None:
        super().__init__()
        self._memory = memory_store
        self._query_service = query_service
        self._top_k = top_k

    async def execute(self, task: str, context: dict[str, Any] | None = None) -> StandResult:
        """Search pipeline: memory recall + SMAK query → consolidated results."""
        self._status = StandStatus.ACTIVE
        logger.info("HIEROPHANT GREEN activated — task_id=%s", self._task_id)

        ctx = context or {}
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
                smak_results = self._query_service.query(task, top_k=top_k, index_name=index_name)
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
                return self._succeed("HIEROPHANT GREEN found no relevant information.", total_hits=0)

            lines: list[str] = []
            for i, hit in enumerate(results["memory_hits"], 1):
                lines.append(f"[Memory #{i}] {hit['content']}")
            for i, hit in enumerate(results["smak_hits"], 1):
                lines.append(f"[SMAK #{i}] ({hit['source_type']}) {hit['content']}")

            return self._succeed("\n---\n".join(lines), total_hits=total, raw=results)

        except Exception as exc:
            logger.exception("HIEROPHANT GREEN failed — task_id=%s", self._task_id)
            return self._fail(str(exc))
