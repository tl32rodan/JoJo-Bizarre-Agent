"""Spawnable Stands — sub-agents summoned by Gold Experience (JoJo Stand persona).

These are NOT JoJo Stands (personas). These are independent agents that
Gold Experience can spawn to handle specific sub-tasks:

  - THE WORLD          (ザ・ワールド)           Close-Range Power — deep reasoning (in-process)
  - HIEROPHANT GREEN   (法皇の緑)               Long-Range — RAG retrieval (subagent)
  - HARVEST            (ハーヴェスト)           Colony — parallel execution (in-process)
  - SHEER HEART ATTACK (シアーハートアタック)     Automatic — background tasks (subagent)
"""

from jojo.stands.base import Stand, StandType, StandResult, StandStatus, SpawnMode

__all__ = ["Stand", "StandType", "StandResult", "StandStatus", "SpawnMode"]
