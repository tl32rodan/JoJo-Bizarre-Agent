"""SubAgentBackend — Strategy interface for sub-agent execution.

Any backend that can spawn, poll, collect, and abort tasks implements
this Protocol.  Gold Experience and Sheer Heart Attack depend on this
abstraction, never on a concrete backend directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class TaskResult:
    handle_id: str
    status: TaskStatus
    output: Any = None
    error: str | None = None


@runtime_checkable
class SubAgentBackend(Protocol):
    """Strategy interface — any sub-agent execution backend."""

    async def spawn(
        self,
        task: str,
        *,
        agent: str = "default",
        tools: list[str] | None = None,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Start a task.  Returns a handle ID."""
        ...

    async def poll(self, handle_id: str) -> TaskStatus:
        """Check status without blocking."""
        ...

    async def collect(self, handle_id: str, timeout: float = 300) -> TaskResult:
        """Block until done, return result."""
        ...

    async def abort(self, handle_id: str) -> None:
        """Cancel a running task."""
        ...

    async def cleanup(self, handle_id: str) -> None:
        """Free resources associated with a handle."""
        ...
