"""Base Stand class and shared types for the Stand system."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StandType(Enum):
    """Spawnable Stands — summoned by Gold Experience as sub-agents."""
    THE_WORLD = "the_world"
    HIEROPHANT_GREEN = "hierophant_green"
    HARVEST = "harvest"
    SHEER_HEART_ATTACK = "sheer_heart_attack"


class StandStatus(Enum):
    SUMMONED = "summoned"
    ACTIVE = "active"
    RETIRED = "retired"
    FAILED = "failed"


class SpawnMode(Enum):
    """How a Stand is executed."""
    IN_PROCESS = "in_process"
    SUBAGENT = "subagent"


STAND_PROFILES: dict[StandType, dict[str, str]] = {
    StandType.THE_WORLD: {
        "name": "THE WORLD（ザ・ワールド）",
        "ability": "Close-Range Power",
        "spawn_mode": "in_process",
        "description": (
            "Stops time for deep, multi-step chain-of-thought reasoning. "
            "Best for complex analysis requiring concentrated cognitive force."
        ),
    },
    StandType.HIEROPHANT_GREEN: {
        "name": "HIEROPHANT GREEN（法皇の緑）",
        "ability": "Long-Range",
        "spawn_mode": "subagent",
        "description": (
            "Extends an Emerald Splash across knowledge bases for semantic "
            "retrieval and RAG search. Spawned as a subagent process."
        ),
    },
    StandType.HARVEST: {
        "name": "HARVEST（ハーヴェスト）",
        "ability": "Colony",
        "spawn_mode": "in_process",
        "description": (
            "Splits into many small units that work in parallel. "
            "Best for batch operations and concurrent sub-tasks."
        ),
    },
    StandType.SHEER_HEART_ATTACK: {
        "name": "SHEER HEART ATTACK（シアーハートアタック）",
        "ability": "Automatic",
        "spawn_mode": "subagent",
        "description": (
            "An autonomous bomb that tracks its target without user control. "
            "Spawned as a fire-and-forget background subagent process."
        ),
    },
}


@dataclass
class StandResult:
    stand_type: StandType
    task_id: str
    status: StandStatus
    output: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class Stand(ABC):
    """Abstract base for all Stands."""

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
        ...

    def _succeed(self, output: Any, **meta: Any) -> StandResult:
        self._status = StandStatus.RETIRED
        return StandResult(
            stand_type=self.stand_type, task_id=self._task_id,
            status=StandStatus.RETIRED, output=output, metadata=meta,
        )

    def _fail(self, error: str, **meta: Any) -> StandResult:
        self._status = StandStatus.FAILED
        return StandResult(
            stand_type=self.stand_type, task_id=self._task_id,
            status=StandStatus.FAILED, error=error, metadata=meta,
        )
