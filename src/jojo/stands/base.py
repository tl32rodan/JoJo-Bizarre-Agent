"""Base Stand class and shared types for the Stand system.

Stand  = the agent entity   (e.g. STAR PLATINUM, THE WORLD)
Ability = what it does       (e.g. Precision ReAct, Time Stop)

Every Stand has exactly one primary ability that defines its pipeline.
JoJo can channel any Stand — there is no hierarchy among them.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StandType(Enum):
    """All available Stands."""
    STAR_PLATINUM = "star_platinum"         # Executor: Ora Ora Rush + The World
    GOLD_EXPERIENCE = "gold_experience"    # Orchestrator: Life Giver + Life Sensor
    HIEROPHANT_GREEN = "hierophant_green"  # Researcher: Emerald Splash + 20m Barrier
    CRAZY_DIAMOND = "crazy_diamond"        # Reviewer: Restoration + Breakdown
    SHEER_HEART_ATTACK = "sheer_heart_attack"  # Background: Automatic Tracking


class StandStatus(Enum):
    SUMMONED = "summoned"
    ACTIVE = "active"
    RETIRED = "retired"
    FAILED = "failed"


class SpawnMode(Enum):
    """How a Stand is executed."""
    IN_PROCESS = "in_process"
    SUBAGENT = "subagent"


@dataclass(frozen=True)
class StandProfile:
    """Separates Stand identity from its ability."""
    name: str
    name_jp: str
    user: str
    part: int
    ability_name: str
    ability_description: str
    spawn_mode: SpawnMode = SpawnMode.IN_PROCESS


STAND_PROFILES: dict[StandType, StandProfile] = {
    StandType.STAR_PLATINUM: StandProfile(
        name="STAR PLATINUM",
        name_jp="スタープラチナ",
        user="Jotaro Kujo",
        part=3,
        ability_name="Ora Ora Rush + The World",
        ability_description=(
            "Direct ReAct executor. Ora Ora Rush for fast building, "
            "Star Platinum: The World for deep reasoning."
        ),
        spawn_mode=SpawnMode.IN_PROCESS,
    ),
    StandType.GOLD_EXPERIENCE: StandProfile(
        name="GOLD EXPERIENCE",
        name_jp="ゴールド・エクスペリエンス",
        user="Giorno Giovanna",
        part=5,
        ability_name="Life Giver + Life Sensor",
        ability_description=(
            "Orchestrates complex tasks. Spawns sub-agents, monitors status, "
            "examines output. Cherishes all life it creates."
        ),
        spawn_mode=SpawnMode.IN_PROCESS,
    ),
    StandType.HIEROPHANT_GREEN: StandProfile(
        name="HIEROPHANT GREEN",
        name_jp="法皇の緑",
        user="Noriaki Kakyoin",
        part=3,
        ability_name="Emerald Splash + 20m Emerald Barrier",
        ability_description=(
            "Deep research via RAG (Emerald Splash) and methodology "
            "enforcement via SKILL.md patterns (20m Barrier). Read-only."
        ),
        spawn_mode=SpawnMode.IN_PROCESS,
    ),
    StandType.CRAZY_DIAMOND: StandProfile(
        name="CRAZY DIAMOND",
        name_jp="クレイジー・ダイヤモンド",
        user="Josuke Higashikata",
        part=4,
        ability_name="Restoration + Breakdown",
        ability_description=(
            "Code review and quality gate. Restoration detects bugs and "
            "fixes them. Breakdown verifies output against requirements."
        ),
        spawn_mode=SpawnMode.IN_PROCESS,
    ),
    StandType.SHEER_HEART_ATTACK: StandProfile(
        name="SHEER HEART ATTACK",
        name_jp="シアーハートアタック",
        user="Yoshikage Kira",
        part=4,
        ability_name="Automatic Tracking",
        ability_description="Fire-and-forget background tasks via SubAgentBackend.",
        spawn_mode=SpawnMode.SUBAGENT,
    ),
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
    """Abstract base for all Stands.

    Subclass this to add new Stands — implement `execute()` with
    whatever pipeline your ability requires.
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
    def profile(self) -> StandProfile:
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
