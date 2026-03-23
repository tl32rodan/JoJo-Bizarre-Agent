"""Memory compaction — post-task learning for Gold Experience.

After completing a complex task, Gold Experience calls the compactor
to extract lessons learned and store them as compact memory entries.
This enables JoJo to learn from experience over time.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_COMPACT_PROMPT = """You are a learning assistant.  Given a completed task and its results,
extract lessons learned in 2-3 concise bullet points.

Focus on:
- What approach worked (or didn't)
- Any patterns or techniques worth remembering
- Mistakes to avoid next time

Task: {task}

Results:
{results}

Lessons learned (concise bullet points):"""


class MemoryCompactor:
    """Extract lessons from completed tasks and store in memory."""

    def __init__(self, llm: Any, memory_store: Any) -> None:
        self._llm = llm
        self._memory = memory_store

    async def compact(
        self,
        task: str,
        results: list[dict[str, Any]],
        tags: dict[str, Any] | None = None,
    ) -> str | None:
        """Extract lessons and store as a compact memory entry.

        Returns the memory UID if stored, None on failure.
        """
        if not results:
            return None

        # Format results for the LLM
        result_text = "\n".join(
            f"- [{r.get('stand', '?')}] {str(r.get('output', r.get('error', '')))[:300]}"
            for r in results
        )

        prompt = _COMPACT_PROMPT.format(
            task=task[:500],
            results=result_text[:2000],
        )

        try:
            response = self._llm.invoke([{"role": "user", "content": prompt}])
            lessons = str(response.content) if hasattr(response, "content") else str(response)

            # Store as a lesson entry
            uid = self._memory.store(
                f"[Lesson] {lessons.strip()}",
                {
                    "type": "lesson",
                    "original_task": task[:200],
                    **(tags or {}),
                },
            )
            logger.info("MemoryCompactor: stored lesson %s", uid)
            return uid

        except Exception as exc:
            logger.debug("MemoryCompactor failed (non-critical): %s", exc)
            return None
