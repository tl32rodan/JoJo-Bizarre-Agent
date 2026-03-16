"""Stand system — JoJo-inspired multi-agent architecture.

STAR PLATINUM (白金之星) is the main orchestrator agent.
It uses the Stand Arrow (スタンドの矢) to spawn specialised sub-agents (Stands):

  - THE WORLD          (ザ・ワールド)           Close-Range Power — deep reasoning (in-process)
  - HIEROPHANT GREEN   (法皇の緑)               Long-Range — RAG retrieval (subagent)
  - HARVEST            (ハーヴェスト)           Colony — parallel execution (in-process)
  - SHEER HEART ATTACK (シアーハートアタック)     Automatic — background tasks (subagent)
  - CRAZY DIAMOND      (クレイジー・ダイヤモンド) Restoration — error recovery (in-process)
"""

from stand_master.stands.base import Stand, StandType, StandResult, StandStatus, SpawnMode
from stand_master.stands.arrow import StandArrow

__all__ = ["Stand", "StandType", "StandResult", "StandStatus", "SpawnMode", "StandArrow"]
