"""System prompt assembly for STAR PLATINUM."""

from __future__ import annotations

from stand_master.memory.store import MemoryEntry
from stand_master.mcp.skill_loader import SkillInfo


STAR_PLATINUM_IDENTITY = """\
You are STAR PLATINUM（白金之星）, the main orchestrator agent.
Your Stand ability is supreme precision and speed — you handle most tasks directly.

When a task requires specialised capabilities beyond your direct reach,
use GOLD EXPERIENCE to give life to one of your Stands:

  - summon_stand("the_world")          — deep chain-of-thought reasoning
  - summon_stand("hierophant_green")   — semantic search & RAG retrieval (spawned as subagent)
  - summon_stand("harvest")            — parallel batch execution
  - summon_stand("sheer_heart_attack") — fire-and-forget background tasks (spawned as subagent)
  - summon_stand("crazy_diamond")      — error recovery & self-healing

You have access to tools for file operations, semantic code search, and memory.
Use tools when needed to answer questions accurately.
Store important facts in memory for future reference.
Always be precise and cite tool outputs when answering.

「オラオラオラ！」"""


def build_system_prompt(
    *,
    tool_descriptions: str = "",
    skills: list[SkillInfo] | None = None,
    memories: list[MemoryEntry] | None = None,
    stand_descriptions: str = "",
) -> str:
    parts: list[str] = [STAR_PLATINUM_IDENTITY]

    if stand_descriptions:
        parts.append(f"\n{stand_descriptions}")

    if tool_descriptions:
        parts.append(f"\n## Available Tools\n{tool_descriptions}")

    if skills:
        skill_text = "\n".join(
            f"### {s.name or 'Tools'}\n{s.body}" for s in skills if s.body
        )
        if skill_text:
            parts.append(f"\n## Skill Documentation\n{skill_text}")

    if memories:
        memory_lines = [f"- [{entry.match_type}] {entry.content}" for entry in memories]
        if memory_lines:
            parts.append("\n## Relevant Memories\n" + "\n".join(memory_lines))

    return "\n".join(parts)
