"""Base Stand class and shared types for the Stand system."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StandType(Enum):
    """The four Stand archetypes."""

    THE_WORLD = "the_world"                   # Close-Range Power
    HIEROPHANT_GREEN = "hierophant_green"      # Long-Range
    HARVEST = "harvest"                        # Colony
    SHEER_HEART_ATTACK = "sheer_heart_attack"  # Automatic


class StandStatus(Enum):
    """Lifecycle status of a Stand invocation."""

    SUMMONED = "summoned"
    ACTIVE = "active"
    RETIRED = "retired"
    FAILED = "failed"


# ── Stand metadata (displayed by STAR PLATINUM when listing abilities) ──────

STAND_PROFILES: dict[StandType, dict[str, str]] = {
    StandType.THE_WORLD: {
        "name": "THE WORLD（ザ・ワールド）",
        "ability": "Close-Range Power",
        "description": (
            "Stops time for deep, multi-step chain-of-thought reasoning. "
            "Best for complex analysis requiring concentrated cognitive force."
        ),
    },
    StandType.HIEROPHANT_GREEN: {
        "name": "HIEROPHANT GREEN（法皇の緑）",
        "ability": "Long-Range",
        "description": (
            "Extends an Emerald Splash across knowledge bases for semantic "
            "retrieval and RAG search. Best for information gathering."
        ),
    },
    StandType.HARVEST: {
        "name": "HARVEST（ハーヴェスト）",
        "ability": "Colony",
        "description": (
            "Splits into many small units that work in parallel. "
            "Best for batch operations and concurrent sub-tasks."
        ),
    },
    StandType.SHEER_HEART_ATTACK: {
        "name": "SHEER HEART ATTACK（シアーハートアタック）",
        "ability": "Automatic",
        "description": (
            "An autonomous bomb that tracks its target without user control. "
            "Best for fire-and-forget background jobs."
        ),
    },
}


@dataclass
class StandResult:
    """Outcome returned when a Stand completes its task."""

    stand_type: StandType
    task_id: str
    status: StandStatus
    output: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class Stand(ABC):
    """Abstract base for all Stands.

    Each Stand is summoned by the Stand Arrow, executes its specialised
    ability, and returns a :class:`StandResult`.
    """

    stand_type: StandType

    def __init__(self) -> None:
        self._task_id: str = uuid.uuid4().hex[:12]
        self._status: StandStatus = StandStatus.SUMMONED

    @property
    def task_id(self) -> str:
        return self._task_id

    @property
    def status(self) -> StandStatus:
        return self._status

    @property
    def profile(self) -> dict[str, str]:
        return STAND_PROFILES[self.stand_type]

    @abstractmethod
    async def execute(self, task: str, context: dict[str, Any] | None = None) -> StandResult:
        """Run this Stand's ability on the given task."""
        ...

    def _succeed(self, output: Any, **meta: Any) -> StandResult:
        self._status = StandStatus.RETIRED
        return StandResult(
            stand_type=self.stand_type,
            task_id=self._task_id,
            status=StandStatus.RETIRED,
            output=output,
            metadata=meta,
        )

    def _fail(self, error: str, **meta: Any) -> StandResult:
        self._status = StandStatus.FAILED
        return StandResult(
            stand_type=self.stand_type,
            task_id=self._task_id,
            status=StandStatus.FAILED,
            error=error,
            metadata=meta,
        )
