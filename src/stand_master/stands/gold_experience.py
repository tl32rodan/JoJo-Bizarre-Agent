"""GOLD EXPERIENCE（ゴールド・エクスペリエンス）— Stand spawner.

Giorno Giovanna's Stand ability: bestowing life.
GOLD EXPERIENCE gives life to new Stands — it is the mechanism
STAR PLATINUM uses to summon specialised sub-agents.

For in-process Stands (THE WORLD, HARVEST, CRAZY DIAMOND), it creates
instances directly.  For subagent Stands (HIEROPHANT GREEN, SHEER HEART
ATTACK), it delegates to the SubAgentSpawner.
"""

from __future__ import annotations

import logging
from typing import Any

from stand_master.stands.base import Stand, StandType, SpawnMode, STAND_PROFILES

logger = logging.getLogger(__name__)


class GoldExperience:
    """「無駄無駄無駄！」— Bestows life upon new Stands."""

    def __init__(
        self,
        *,
        llm: Any = None,
        reasoning_llm: Any = None,
        tool_registry: Any = None,
        memory_store: Any = None,
        query_service: Any = None,
        subagent_spawner: Any = None,
        harvest_worker: Any = None,
        config: Any = None,
    ) -> None:
        self._llm = llm
        self._reasoning_llm = reasoning_llm
        self._tools = tool_registry
        self._memory = memory_store
        self._query_service = query_service
        self._spawner = subagent_spawner
        self._harvest_worker = harvest_worker
        self._config = config
        self._active_stands: list[Stand] = []

    def summon(self, stand_type: StandType) -> Stand:
        logger.info("GOLD EXPERIENCE gives life — summoning %s", STAND_PROFILES[stand_type]["name"])

        if stand_type == StandType.THE_WORLD:
            from stand_master.stands.the_world import TheWorld
            stand = TheWorld(
                llm=self._reasoning_llm or self._llm,
                tool_registry=self._tools,
                max_steps=30,
            )

        elif stand_type == StandType.HIEROPHANT_GREEN:
            from stand_master.stands.hierophant_green import HierophantGreen
            stand = HierophantGreen(
                memory_store=self._memory,
                query_service=self._query_service,
                top_k=10,
            )

        elif stand_type == StandType.HARVEST:
            from stand_master.stands.harvest import Harvest
            max_c = self._config.subagent.max_concurrent if self._config else 10
            stand = Harvest(worker=self._harvest_worker, max_concurrency=max_c)

        elif stand_type == StandType.SHEER_HEART_ATTACK:
            from stand_master.stands.sheer_heart_attack import SheerHeartAttack
            timeout = self._config.subagent.timeout_seconds if self._config else 600
            stand = SheerHeartAttack(spawner=self._spawner, timeout=timeout)

        elif stand_type == StandType.CRAZY_DIAMOND:
            from stand_master.stands.crazy_diamond import CrazyDiamond
            stand = CrazyDiamond(
                llm=self._llm,
                tool_registry=self._tools,
                memory_store=self._memory,
            )

        else:
            raise ValueError(f"Unknown Stand type: {stand_type}")

        self._active_stands.append(stand)
        return stand

    def summon_by_name(self, name: str) -> Stand:
        try:
            stand_type = StandType(name.lower().strip())
        except ValueError:
            name_lower = name.lower()
            for st in StandType:
                profile = STAND_PROFILES[st]
                if name_lower in profile["name"].lower() or name_lower == st.name.lower():
                    stand_type = st
                    break
            else:
                raise ValueError(
                    f"Unknown Stand name: '{name}'. "
                    f"Available: {[st.value for st in StandType]}"
                )
        return self.summon(stand_type)

    def get_spawn_mode(self, stand_type: StandType) -> SpawnMode:
        mode = STAND_PROFILES[stand_type].get("spawn_mode", "in_process")
        return SpawnMode(mode)

    @property
    def active_stands(self) -> list[Stand]:
        return list(self._active_stands)

    def retire_all(self) -> None:
        self._active_stands.clear()

    @staticmethod
    def describe_stands() -> str:
        lines = ["## GOLD EXPERIENCE — Available Stands\n"]
        for st in StandType:
            p = STAND_PROFILES[st]
            mode = p.get("spawn_mode", "in_process")
            lines.append(f"### {p['name']}  [{p['ability']}]  (mode: {mode})")
            lines.append(f"{p['description']}\n")
            lines.append(f"Summon command: `summon_stand(\"{st.value}\")`\n")
        return "\n".join(lines)
