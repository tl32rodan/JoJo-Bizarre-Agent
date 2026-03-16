"""Tests for react_agent.memory.summarizer."""

from __future__ import annotations

import pytest

from react_agent.memory.summarizer import ConversationSummarizer


class FakeSummarizerLLM:
    def invoke(self, prompt: str) -> str:
        return "This is a summary of the conversation."


class TestConversationSummarizer:
    def test_summarize_long_conversation(self):
        messages = [
            {"role": "system", "content": "You are helpful."},
        ] + [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"Turn {i}"}
            for i in range(30)
        ]
        summarizer = ConversationSummarizer(FakeSummarizerLLM(), threshold_turns=20)
        assert summarizer.should_summarize(messages) is True
        result = summarizer.summarize(messages)
        assert "summary" in result.summary.lower()
        assert result.original_turn_count == 30

    def test_skip_short_conversation(self):
        messages = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
        ]
        summarizer = ConversationSummarizer(FakeSummarizerLLM(), threshold_turns=20)
        assert summarizer.should_summarize(messages) is False

    def test_system_messages_excluded_from_count(self):
        messages = [
            {"role": "system", "content": "System prompt"},
        ] * 50
        summarizer = ConversationSummarizer(FakeSummarizerLLM(), threshold_turns=20)
        assert summarizer.should_summarize(messages) is False
