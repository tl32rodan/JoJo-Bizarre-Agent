"""Shared prompt utilities.

Each Stand builds its own system prompt. This module provides
reusable formatting helpers.
"""

from __future__ import annotations

from typing import Any


def format_memories(memories: list[Any] | None) -> str:
    """Format memory entries for injection into system prompts."""
    if not memories:
        return ""
    lines = [f"- [{getattr(e, 'match_type', 'memory')}] {getattr(e, 'content', str(e))}" for e in memories]
    return "\n## Relevant Memories\n" + "\n".join(lines)
