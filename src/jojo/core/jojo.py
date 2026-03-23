"""JoJo（ジョジョ）— Main orchestrator.

JoJo decides which Stand to channel based on the task, then delegates
execution to that Stand's `execute()` method.

- Star Platinum is the default for general tasks (building).
- Gold Experience is chosen when sub-agent orchestration is needed.
- Hierophant Green is chosen for research / analysis / planning.
- Crazy Diamond is chosen for code review / quality checks.
- JoJo can channel ANY registered Stand — no hierarchy.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from jojo.stands.base import Stand, StandType, StandResult, STAND_PROFILES

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class JoJoResult:
    answer: str
    stand: str
    steps: int = 0
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    stands_summoned: list[str] = field(default_factory=list)


# Keyword hints for auto-selecting a Stand
_STAND_HINTS: dict[StandType, list[str]] = {
    StandType.GOLD_EXPERIENCE: [
        "spawn", "orchestrate", "complex", "multi-step", "parallel",
        "sub-agent", "subagent", "delegate", "break down", "coordinate",
    ],
    StandType.HIEROPHANT_GREEN: [
        "research", "investigate", "analyze", "analyse", "study",
        "explore", "search", "find out", "look into", "deep dive",
        "plan", "design", "architecture", "methodology",
    ],
    StandType.CRAZY_DIAMOND: [
        "review", "check", "fix", "bug", "quality", "audit",
        "verify", "validate", "test", "lint", "inspect",
    ],
    StandType.STAR_PLATINUM: [],  # default fallback
}


class JoJo:
    """The main JoJo protagonist — channels Stands.

    「やれやれだぜ…」
    """

    def __init__(self, memory: Any, config: Any) -> None:
        self._memory = memory
        self._config = config
        self._stands: dict[StandType, Stand] = {}
        self._current_stand: StandType | None = None

    def register_stand(self, stand: Stand) -> None:
        """Register a Stand that JoJo can channel."""
        self._stands[stand.stand_type] = stand

    @property
    def current_stand(self) -> StandType | None:
        return self._current_stand

    @property
    def available_stands(self) -> list[StandType]:
        return list(self._stands.keys())

    def choose_stand(self, user_input: str) -> StandType:
        """Auto-select the best Stand for the task."""
        input_lower = user_input.lower()

        for stand_type, hints in _STAND_HINTS.items():
            if stand_type not in self._stands:
                continue
            for hint in hints:
                if hint in input_lower:
                    return stand_type

        # Default to Star Platinum
        if StandType.STAR_PLATINUM in self._stands:
            return StandType.STAR_PLATINUM

        # Fallback to first registered stand
        return next(iter(self._stands))

    async def run(
        self,
        user_input: str,
        *,
        stand: StandType | None = None,
        time_stop: bool = False,
        barrier: bool = False,
        review: bool = False,
        max_steps: int | None = None,
    ) -> JoJoResult:
        """Process user input through the chosen Stand."""
        chosen = stand or self.choose_stand(user_input)
        if chosen not in self._stands:
            chosen = StandType.STAR_PLATINUM

        self._current_stand = chosen
        stand_instance = self._stands[chosen]
        profile = STAND_PROFILES[chosen]

        logger.info("JoJo channels %s（%s）", profile.name, profile.name_jp)

        context: dict[str, Any] = {}
        if max_steps:
            context["max_steps"] = max_steps
        if time_stop:
            context["time_stop"] = True
        if barrier:
            context["mode"] = "barrier"
        if review:
            context["mode"] = "restoration"
        if hasattr(self._config, "session"):
            context["max_history_tokens"] = self._config.session.max_history_tokens

        result: StandResult = await stand_instance.execute(user_input, context)

        # Auto-memorize
        if hasattr(self._config, "memory") and self._config.memory.auto_memorize:
            if result.metadata.get("tool_calls"):
                self._memory.store(
                    f"Q: {user_input}\nA: {str(result.output)[:300]}",
                    {"type": "conversation", "stand": chosen.value},
                )

        return JoJoResult(
            answer=str(result.output) if result.output else (result.error or "No output."),
            stand=profile.name,
            steps=result.metadata.get("steps", 0),
            tool_calls=result.metadata.get("tool_calls", []),
            stands_summoned=result.metadata.get("stands_used", []),
        )
