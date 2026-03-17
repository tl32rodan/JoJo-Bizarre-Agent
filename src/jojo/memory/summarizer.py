"""Conversation summarizer for context window management."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class LLMClient(Protocol):
    def invoke(self, prompt: str) -> str: ...


SUMMARIZE_PROMPT = """Summarize the following conversation into a concise paragraph.
Preserve key facts, decisions, and action items.

Conversation:
{conversation}

Summary:"""


@dataclass(frozen=True)
class SummaryResult:
    summary: str
    original_turn_count: int


class ConversationSummarizer:
    def __init__(self, llm: LLMClient, threshold_turns: int = 20) -> None:
        self._llm = llm
        self._threshold = threshold_turns

    def should_summarize(self, messages: list[dict[str, Any]]) -> bool:
        turns = sum(1 for m in messages if m.get("role") in ("user", "assistant"))
        return turns >= self._threshold

    def summarize(self, messages: list[dict[str, Any]]) -> SummaryResult:
        parts: list[str] = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if role == "system":
                continue
            parts.append(f"{role}: {content}")

        prompt = SUMMARIZE_PROMPT.format(conversation="\n".join(parts))
        summary = self._llm.invoke(prompt)
        return SummaryResult(summary=summary.strip(), original_turn_count=len(parts))
