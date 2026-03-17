"""System prompt utilities for JoJo.

Note: Each JoJo Stand persona now builds its own system prompt via
`build_system_prompt()`. This module provides shared helpers.
"""

from __future__ import annotations

from jojo.memory.store import MemoryEntry
from jojo.mcp.skill_loader import SkillInfo


def format_memories(memories: list[MemoryEntry] | None) -> str:
    """Format memory entries for injection into system prompts."""
    if not memories:
        return ""
    lines = [f"- [{entry.match_type}] {entry.content}" for entry in memories]
    return "\n## Relevant Memories\n" + "\n".join(lines)


def format_skills(skills: list[SkillInfo] | None) -> str:
    """Format SKILL.md documentation for injection into system prompts."""
    if not skills:
        return ""
    parts = [f"### {s.name or 'Tools'}\n{s.body}" for s in skills if s.body]
    if not parts:
        return ""
    return "\n## Skill Documentation\n" + "\n".join(parts)
