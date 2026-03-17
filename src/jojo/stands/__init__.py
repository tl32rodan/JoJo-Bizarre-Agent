"""Stand system — JoJo's multi-agent architecture.

Stand  = the agent entity  (e.g. STAR PLATINUM, THE WORLD)
Ability = what it does      (e.g. Precision, Time Stop, Colony)

  - STAR PLATINUM       — Precision + Time Stop (default ReAct agent)
  - GOLD EXPERIENCE     — Life Giver (sub-agent spawner)
  - THE WORLD           — Time Stop (deep reasoning, spawnable)
  - HIEROPHANT GREEN    — Emerald Splash (RAG retrieval)
  - HARVEST             — Colony (parallel execution)
  - SHEER HEART ATTACK  — Automatic (background tasks)
"""

from jojo.stands.base import Stand, StandType, StandResult, StandStatus, SpawnMode, StandProfile

__all__ = ["Stand", "StandType", "StandResult", "StandStatus", "SpawnMode", "StandProfile"]
