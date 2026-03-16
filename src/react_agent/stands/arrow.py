"""Stand Arrow（スタンドの矢）— Stand factory.

The Stand Arrow is the mechanism STAR PLATINUM uses to summon Stands.
It analyses the task, selects the appropriate Stand type, and creates
a fully-initialised Stand instance ready for execution.
"""

from __future__ import annotations

import logging
from typing import Any

from react_agent.stands.base import Stand, StandType, STAND_PROFILES

logger = logging.getLogger(__name__)


class StandArrow:
    """Factory that pierces a task and awakens the correct Stand.

    Usage::

        arrow = StandArrow(llm=llm, memory=memory, ...)
        stand = arrow.summon(StandType.THE_WORLD)
        result = await stand.execute("analyse this circuit", context={...})
    """

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
        """Create and return the requested Stand type."""
        logger.info(
            "Stand Arrow pierces — summoning %s",
            STAND_PROFILES[stand_type]["name"],
        )

        if stand_type == StandType.THE_WORLD:
            from react_agent.stands.the_world import TheWorld

            # Use reasoning LLM if available, otherwise default LLM.
            llm = self._reasoning_llm or self._llm
            stand = TheWorld(
                llm=llm,
                tool_registry=self._tools,
                max_steps=30,
            )

        elif stand_type == StandType.HIEROPHANT_GREEN:
            from react_agent.stands.hierophant_green import HierophantGreen

            stand = HierophantGreen(
                memory_store=self._memory,
                query_service=self._query_service,
                top_k=10,
            )

        elif stand_type == StandType.HARVEST:
            from react_agent.stands.harvest import Harvest

            stand = Harvest(
                worker=self._harvest_worker,
                max_concurrency=self._config.subagent.max_concurrent if self._config else 10,
            )

        elif stand_type == StandType.SHEER_HEART_ATTACK:
            from react_agent.stands.sheer_heart_attack import SheerHeartAttack

            stand = SheerHeartAttack(
                spawner=self._spawner,
                timeout=self._config.subagent.timeout_seconds if self._config else 600,
            )

        else:
            raise ValueError(f"Unknown Stand type: {stand_type}")

        self._active_stands.append(stand)
        return stand

    def summon_by_name(self, name: str) -> Stand:
        """Summon a Stand by its string name (e.g. ``"the_world"``)."""
        try:
            stand_type = StandType(name.lower().strip())
        except ValueError:
            # Try matching display names.
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

    @property
    def active_stands(self) -> list[Stand]:
        return list(self._active_stands)

    def retire_all(self) -> None:
        """Mark all active Stands as retired."""
        self._active_stands.clear()

    @staticmethod
    def describe_stands() -> str:
        """Return a formatted description of all available Stands.

        Used by STAR PLATINUM's system prompt to know what it can summon.
        """
        lines = ["## Stand Arrow — Available Stands\n"]
        for st in StandType:
            p = STAND_PROFILES[st]
            lines.append(f"### {p['name']}  [{p['ability']}]")
            lines.append(f"{p['description']}\n")
            lines.append(f"Summon command: `summon_stand(\"{st.value}\")`\n")
        return "\n".join(lines)
