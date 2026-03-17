"""JoJo Stands — protagonist persona system.

JoJo can 'become' any of these Stands, each with its own philosophy:

  Part 3 · STAR PLATINUM     — precision & direct execution
  Part 4 · CRAZY DIAMOND     — restoration & error recovery
  Part 5 · GOLD EXPERIENCE   — sub-agent spawning & orchestration
  Part 6 · STONE FREE        — decomposition & connection-finding
  Part 7 · TUSK              — iterative deepening research
  Part 8 · SOFT & WET        — extraction & property isolation
"""

from jojo.jojo_stands.base import JoJoStand, JoJoStandType, StandProfile, JOJO_STAND_PROFILES
from jojo.jojo_stands.star_platinum import StarPlatinum
from jojo.jojo_stands.crazy_diamond import CrazyDiamond
from jojo.jojo_stands.gold_experience import GoldExperience
from jojo.jojo_stands.stone_free import StoneFree
from jojo.jojo_stands.tusk import Tusk
from jojo.jojo_stands.soft_and_wet import SoftAndWet

JOJO_STAND_CLASSES: dict[JoJoStandType, type[JoJoStand]] = {
    JoJoStandType.STAR_PLATINUM: StarPlatinum,
    JoJoStandType.CRAZY_DIAMOND: CrazyDiamond,
    JoJoStandType.GOLD_EXPERIENCE: GoldExperience,
    JoJoStandType.STONE_FREE: StoneFree,
    JoJoStandType.TUSK: Tusk,
    JoJoStandType.SOFT_AND_WET: SoftAndWet,
}

__all__ = [
    "JoJoStand", "JoJoStandType", "StandProfile", "JOJO_STAND_PROFILES",
    "JOJO_STAND_CLASSES",
    "StarPlatinum", "CrazyDiamond", "GoldExperience",
    "StoneFree", "Tusk", "SoftAndWet",
]
