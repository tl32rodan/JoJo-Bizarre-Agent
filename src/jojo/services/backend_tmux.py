"""TmuxBackend — wraps the existing SubAgentSpawner behind SubAgentBackend.

This is a thin adapter so Gold Experience / Sheer Heart Attack can use
the legacy tmux/cron spawner through the new protocol.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from jojo.services.backend import SubAgentBackend, TaskResult, TaskStatus
from jojo.services.subagent import SubAgentSpawner, SubAgentStatus

logger = logging.getLogger(__name__)

_STATUS_MAP = {
    SubAgentStatus.PENDING: TaskStatus.PENDING,
    SubAgentStatus.RUNNING: TaskStatus.RUNNING,
    SubAgentStatus.COMPLETED: TaskStatus.COMPLETED,
    SubAgentStatus.FAILED: TaskStatus.FAILED,
}


class TmuxBackend:
    """Adapter: SubAgentSpawner → SubAgentBackend protocol."""

    def __init__(self, spawner: SubAgentSpawner) -> None:
        self._spawner = spawner
        self._handles: dict[str, Any] = {}  # handle_id → SubAgentHandle

    async def spawn(
        self,
        task: str,
        *,
        agent: str = "default",
        tools: list[str] | None = None,
        context: dict[str, Any] | None = None,
    ) -> str:
        handle = self._spawner.spawn(task, context=context)
        self._handles[handle.task_id] = handle
        return handle.task_id

    async def poll(self, handle_id: str) -> TaskStatus:
        handle = self._handles.get(handle_id)
        if handle is None:
            return TaskStatus.FAILED
        raw = self._spawner.poll(handle)
        return _STATUS_MAP.get(raw, TaskStatus.PENDING)

    async def collect(self, handle_id: str, timeout: float = 300) -> TaskResult:
        handle = self._handles.get(handle_id)
        if handle is None:
            return TaskResult(handle_id=handle_id, status=TaskStatus.FAILED, error="Unknown handle")

        elapsed = 0.0
        interval = 5.0
        while elapsed < timeout:
            raw = self._spawner.poll(handle)
            if raw in (SubAgentStatus.COMPLETED, SubAgentStatus.FAILED):
                sub = self._spawner.collect(handle)
                self._handles.pop(handle_id, None)
                return TaskResult(
                    handle_id=handle_id,
                    status=_STATUS_MAP[raw],
                    output=sub.output,
                    error=sub.error,
                )
            await asyncio.sleep(interval)
            elapsed += interval

        self._handles.pop(handle_id, None)
        return TaskResult(handle_id=handle_id, status=TaskStatus.FAILED, error=f"Timeout after {timeout}s")

    async def abort(self, handle_id: str) -> None:
        self._handles.pop(handle_id, None)
        logger.info("TmuxBackend: abort requested for %s (best-effort)", handle_id)

    async def cleanup(self, handle_id: str) -> None:
        self._handles.pop(handle_id, None)
