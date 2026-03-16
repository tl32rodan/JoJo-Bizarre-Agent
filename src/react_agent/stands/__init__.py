"""Stand system — JoJo-inspired multi-agent architecture.

STAR PLATINUM (白金之星) is the main orchestrator agent.
It uses the Stand Arrow (スタンドの矢) to spawn specialised sub-agents (Stands):

  - THE WORLD        (ザ・ワールド)       Close-Range Power — deep ReAct reasoning
  - HIEROPHANT GREEN (法皇の緑)           Long-Range — RAG retrieval & search
  - HARVEST          (ハーヴェスト)       Colony — parallel task execution
  - SHEER HEART ATTACK (シアーハートアタック) Automatic — fire-and-forget background tasks
"""

from react_agent.stands.base import Stand, StandType, StandResult, StandStatus
from react_agent.stands.arrow import StandArrow

__all__ = [
    "Stand",
    "StandType",
    "StandResult",
    "StandStatus",
    "StandArrow",
]
