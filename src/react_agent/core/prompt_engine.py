"""System prompt assembly for the ReAct agent."""

from __future__ import annotations

from react_agent.memory.store import MemoryEntry
from react_agent.mcp.skill_loader import SkillInfo


AGENT_IDENTITY = """You are a local AI assistant running on an internal workstation.
You have access to tools for file operations, semantic code search, and memory.
Use tools when needed to answer questions accurately. Store important facts in memory for future reference.
Always be precise and cite tool outputs when answering."""


def build_system_prompt(
    *,
    tool_descriptions: str = "",
    skills: list[SkillInfo] | None = None,
    memories: list[MemoryEntry] | None = None,
) -> str:
    """Assemble the full system prompt from components."""
    parts: list[str] = [AGENT_IDENTITY]

    if tool_descriptions:
        parts.append(f"\n## Available Tools\n{tool_descriptions}")

    if skills:
        skill_text = "\n".join(
            f"### {s.name or 'Tools'}\n{s.body}" for s in skills if s.body
        )
        if skill_text:
            parts.append(f"\n## Skill Documentation\n{skill_text}")

    if memories:
        memory_lines = []
        for entry in memories:
            memory_lines.append(f"- [{entry.match_type}] {entry.content}")
        if memory_lines:
            parts.append(
                "\n## Relevant Memories\n" + "\n".join(memory_lines)
            )

    return "\n".join(parts)
