"""JoJo（ジョジョ）— Main orchestrator.

JoJo is the protagonist. He can channel any of his JoJo Stand personas
(Star Platinum, Crazy Diamond, Gold Experience, Stone Free, Tusk, Soft & Wet),
each with its own philosophy and system prompt.

JoJo decides which persona to adopt based on the task at hand,
then delegates execution to that persona's `run()` method.

Heartbeat belongs to JoJo — he is always alive, regardless of which
Stand persona is active.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from jojo.config import AgentConfig
from jojo.core.context_manager import ContextManager
from jojo.jojo_stands.base import JoJoStandType, JOJO_STAND_PROFILES
from jojo.memory.store import MemoryStore
from jojo.mcp.tool_registry import ToolRegistry
from jojo.services.permission import PermissionManager, PermissionVerdict

logger = logging.getLogger(__name__)


class ChatModel(Protocol):
    def invoke(self, messages: list[dict[str, Any]]) -> Any: ...
    def bind_tools(self, tools: list[Any]) -> ChatModel: ...


@dataclass(frozen=True)
class ToolCallRecord:
    name: str
    arguments: dict[str, Any]
    result: str


@dataclass(frozen=True)
class JoJoResult:
    answer: str
    persona: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    steps: int = 0
    stands_summoned: list[str] = field(default_factory=list)


# Map natural-language hints to persona types for auto-selection
_PERSONA_HINTS: dict[JoJoStandType, list[str]] = {
    JoJoStandType.STAR_PLATINUM: [
        "quick", "direct", "simple", "execute", "do it", "just",
    ],
    JoJoStandType.CRAZY_DIAMOND: [
        "fix", "repair", "error", "broken", "bug", "heal", "restore", "recover", "debug",
    ],
    JoJoStandType.GOLD_EXPERIENCE: [
        "spawn", "orchestrate", "complex", "multi", "parallel", "search",
        "retrieve", "rag", "background", "sub-agent", "subagent",
    ],
    JoJoStandType.STONE_FREE: [
        "decompose", "analyse", "analyze", "connect", "relate", "unravel",
        "dependency", "architecture", "structure",
    ],
    JoJoStandType.TUSK: [
        "research", "deep", "investigate", "explore", "iterative", "drill",
        "thorough", "comprehensive",
    ],
    JoJoStandType.SOFT_AND_WET: [
        "extract", "refactor", "isolate", "purify", "clean", "strip",
        "simplify", "property",
    ],
}


class JoJo:
    """The main JoJo protagonist — channels different Stand personas.

    「やれやれだぜ…今回はどのスタンドで行くか。」
    """

    def __init__(
        self,
        llm: ChatModel,
        tool_registry: ToolRegistry,
        memory: MemoryStore,
        permissions: PermissionManager,
        config: AgentConfig,
    ) -> None:
        self._llm = llm
        self._tools = tool_registry
        self._memory = memory
        self._permissions = permissions
        self._config = config
        self._personas: dict[JoJoStandType, Any] = {}
        self._current_persona: JoJoStandType | None = None

    def register_persona(self, stand_type: JoJoStandType, persona: Any) -> None:
        """Register a JoJo Stand persona."""
        self._personas[stand_type] = persona

    @property
    def current_persona(self) -> JoJoStandType | None:
        return self._current_persona

    @property
    def available_personas(self) -> list[JoJoStandType]:
        return list(self._personas.keys())

    def choose_persona(self, user_input: str) -> JoJoStandType:
        """Auto-select the best JoJo Stand persona for the task.

        Uses keyword matching as a heuristic. Falls back to Star Platinum
        (the default, direct-execution persona).
        """
        input_lower = user_input.lower()

        scores: dict[JoJoStandType, int] = {st: 0 for st in self._personas}
        for stand_type, hints in _PERSONA_HINTS.items():
            if stand_type not in self._personas:
                continue
            for hint in hints:
                if hint in input_lower:
                    scores[stand_type] += 1

        best = max(scores, key=scores.get)  # type: ignore[arg-type]
        if scores[best] == 0:
            # Default to Star Platinum
            return JoJoStandType.STAR_PLATINUM

        return best

    async def run(
        self,
        user_input: str,
        *,
        persona: JoJoStandType | None = None,
        max_steps: int = 15,
    ) -> JoJoResult:
        """Process user input through the chosen JoJo Stand persona."""
        # Choose persona
        chosen = persona or self.choose_persona(user_input)
        if chosen not in self._personas:
            chosen = JoJoStandType.STAR_PLATINUM

        self._current_persona = chosen
        stand = self._personas[chosen]
        profile = JOJO_STAND_PROFILES[chosen]

        logger.info("JoJo channels %s（%s）", profile.name, profile.name_jp)

        context = {"max_steps": max_steps}
        result = await stand.run(user_input, context)

        # Auto-memorize if configured
        if self._config.memory.auto_memorize and result.get("tool_calls"):
            self._memory.store(
                f"Q: {user_input}\nA: {result['answer'][:300]}",
                {"type": "conversation", "persona": chosen.value},
            )

        return JoJoResult(
            answer=result["answer"],
            persona=profile.name,
            tool_calls=[
                ToolCallRecord(name=tc["name"], arguments=tc.get("arguments", {}), result=tc.get("result", ""))
                for tc in result.get("tool_calls", [])
            ],
            steps=result.get("steps", 0),
            stands_summoned=[
                s.get("stand", "") for s in result.get("stands_summoned", [])
            ],
        )

    def describe_personas(self) -> str:
        """Describe all available JoJo Stand personas."""
        lines = ["## JoJo Stand Personas\n"]
        for st in self._personas:
            p = JOJO_STAND_PROFILES[st]
            lines.append(
                f"- **{p.name}**（{p.name_jp}）— {p.user} (Part {p.part})\n"
                f"  Ability: {p.ability_name} — {p.ability_description}\n"
                f"  Philosophy: {p.philosophy}\n"
            )
        return "\n".join(lines)
