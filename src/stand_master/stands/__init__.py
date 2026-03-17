"""Stand system — JoJo-inspired multi-agent architecture.

STAR PLATINUM (白金之星) is the main orchestrator agent.
It uses GOLD EXPERIENCE (ゴールド・エクスペリエンス) to give life to
specialised sub-agents (Stands):

  - THE WORLD          (ザ・ワールド)           Close-Range Power — deep reasoning (in-process)
  - HIEROPHANT GREEN   (法皇の緑)               Long-Range — RAG retrieval (subagent)
  - HARVEST            (ハーヴェスト)           Colony — parallel execution (in-process)
  - SHEER HEART ATTACK (シアーハートアタック)     Automatic — background tasks (subagent)
  - CRAZY DIAMOND      (クレイジー・ダイヤモンド) Restoration — error recovery (in-process)
"""

from stand_master.stands.base import Stand, StandType, StandResult, StandStatus, SpawnMode
from stand_master.stands.gold_experience import GoldExperience

__all__ = ["Stand", "StandType", "StandResult", "StandStatus", "SpawnMode", "GoldExperience"]
