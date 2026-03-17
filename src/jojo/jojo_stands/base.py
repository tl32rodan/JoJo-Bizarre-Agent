"""JoJo Stand persona base class.

A JoJo Stand is a persona the main JoJo orchestrator can "become".
Each persona has its own philosophy, system prompt, and skill affinity,
but they all share JoJo's memory.

Distinguished from spawnable stands (stands/): JoJo Stands define HOW
JoJo approaches a task; spawnable stands are independent agents created
by Gold Experience.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any


class JoJoStandType(Enum):
    """All JoJo protagonist Stands across seasons."""
    STAR_PLATINUM = "star_platinum"          # Part 3 · Jotaro Kujo
    CRAZY_DIAMOND = "crazy_diamond"          # Part 4 · Josuke Higashikata
    GOLD_EXPERIENCE = "gold_experience"      # Part 5 · Giorno Giovanna
    STONE_FREE = "stone_free"                # Part 6 · Jolyne Cujoh
    TUSK = "tusk"                            # Part 7 · Johnny Joestar
    SOFT_AND_WET = "soft_and_wet"            # Part 8 · Josuke (Gappy)


@dataclass(frozen=True)
class StandProfile:
    """Metadata for a JoJo Stand — the Stand vs its ability."""
    name: str
    name_jp: str
    user: str
    part: int
    ability_name: str
    ability_description: str
    philosophy: str


JOJO_STAND_PROFILES: dict[JoJoStandType, StandProfile] = {
    JoJoStandType.STAR_PLATINUM: StandProfile(
        name="STAR PLATINUM",
        name_jp="スタープラチナ",
        user="Jotaro Kujo",
        part=3,
        ability_name="Star Finger / The World",
        ability_description="Supreme precision, speed, and the ability to stop time.",
        philosophy=(
            "Direct, efficient, no-nonsense. Handle tasks with maximum precision "
            "and minimum wasted steps. やれやれだぜ."
        ),
    ),
    JoJoStandType.CRAZY_DIAMOND: StandProfile(
        name="CRAZY DIAMOND",
        name_jp="クレイジー・ダイヤモンド",
        user="Josuke Higashikata",
        part=4,
        ability_name="Restoration",
        ability_description="Restores anything to a previous state. Cannot heal itself or revive the dead.",
        philosophy=(
            "Diagnose what's broken, find root causes, and restore things to "
            "their proper state. Fix errors, repair pipelines, heal the system."
        ),
    ),
    JoJoStandType.GOLD_EXPERIENCE: StandProfile(
        name="GOLD EXPERIENCE",
        name_jp="ゴールド・エクスペリエンス",
        user="Giorno Giovanna",
        part=5,
        ability_name="Life Giver",
        ability_description="Bestows life upon objects, creating living organisms. Can spawn and manage agents.",
        philosophy=(
            "Break complex tasks into sub-tasks, give life to specialised agents, "
            "monitor their progress, and synthesise their results. 無駄無駄無駄!"
        ),
    ),
    JoJoStandType.STONE_FREE: StandProfile(
        name="STONE FREE",
        name_jp="ストーン・フリー",
        user="Jolyne Cujoh",
        part=6,
        ability_name="String Decomposition",
        ability_description="Unravels body into string to stretch, connect, create barriers, and detect vibrations.",
        philosophy=(
            "Unravel complexity — decompose problems into threads, find connections "
            "between seemingly unrelated things, weave understanding from disparate parts."
        ),
    ),
    JoJoStandType.TUSK: StandProfile(
        name="TUSK",
        name_jp="タスク",
        user="Johnny Joestar",
        part=7,
        ability_name="Infinite Rotation",
        ability_description=(
            "Evolves through Acts 1-4. Act 1: basic shots. Act 2: guided shots. "
            "Act 3: self-guiding. Act 4: infinite rotation — unstoppable, transcends dimensions."
        ),
        philosophy=(
            "Iterative deepening — start with a broad, simple pass, then progressively "
            "drill deeper with each Act. When Act 4 spins, nothing can stop it."
        ),
    ),
    JoJoStandType.SOFT_AND_WET: StandProfile(
        name="SOFT & WET",
        name_jp="ソフト＆ウェット",
        user="Josuke Higashikata (Gappy)",
        part=8,
        ability_name="Bubble Plunder",
        ability_description="Creates bubbles that steal properties from objects — friction, sound, sight, anything.",
        philosophy=(
            "Extract and isolate — plunder the key property from complex data, "
            "strip away noise, and transform what remains. Refactor, extract, purify."
        ),
    ),
}


class JoJoStand(ABC):
    """Abstract base for a JoJo protagonist Stand persona.

    Each JoJo Stand defines:
    - A system prompt (how JoJo thinks when using this persona)
    - A run method (how tasks are processed under this philosophy)
    """

    stand_type: JoJoStandType

    @property
    def profile(self) -> StandProfile:
        return JOJO_STAND_PROFILES[self.stand_type]

    @abstractmethod
    def build_system_prompt(self, tool_descriptions: str, stand_descriptions: str) -> str:
        """Build the system prompt for this persona."""
        ...

    @abstractmethod
    async def run(self, user_input: str, context: dict[str, Any]) -> dict[str, Any]:
        """Process user input under this persona's philosophy.

        Returns a dict with at least {"answer": str, "steps": int}.
        """
        ...
