"""Context window management for LLM conversations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ContextManager:
    """Manage message history to stay within token limits."""

    max_tokens: int = 8000
    _messages: list[dict[str, Any]] = field(default_factory=list)

    def add_message(self, message: dict[str, Any]) -> None:
        self._messages.append(message)

    def get_messages(self) -> list[dict[str, Any]]:
        """Return messages trimmed to fit within max_tokens.

        Strategy: always keep system prompt (first message) and
        recent messages. Drop oldest non-system messages when over limit.
        """
        if not self._messages:
            return []

        total = sum(self._estimate_tokens(m) for m in self._messages)
        if total <= self.max_tokens:
            return list(self._messages)

        # Keep system prompt + trim from the front of conversation.
        system_msgs = [m for m in self._messages if m.get("role") == "system"]
        other_msgs = [m for m in self._messages if m.get("role") != "system"]

        budget = self.max_tokens - sum(self._estimate_tokens(m) for m in system_msgs)
        kept: list[dict[str, Any]] = []
        for msg in reversed(other_msgs):
            cost = self._estimate_tokens(msg)
            if budget - cost < 0 and kept:
                break
            kept.append(msg)
            budget -= cost
        kept.reverse()

        return system_msgs + kept

    def clear(self) -> None:
        self._messages.clear()

    @property
    def message_count(self) -> int:
        return len(self._messages)

    @staticmethod
    def truncate_tool_result(result: str, max_chars: int = 8000) -> str:
        """Truncate a large tool result, keeping head and tail."""
        if len(result) <= max_chars:
            return result
        half = max_chars // 2
        truncated = len(result) - max_chars
        return (
            result[:half]
            + f"\n\n[... truncated {truncated} characters ...]\n\n"
            + result[-half:]
        )

    @staticmethod
    def _estimate_tokens(message: dict[str, Any]) -> int:
        """Rough token estimate: ~3.5 chars per token for mixed CJK/English."""
        content = message.get("content", "")
        if isinstance(content, str):
            return max(1, len(content) // 3)
        return 10  # fallback for non-string content
