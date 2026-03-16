"""Tests for react_agent.core.context_manager."""

from __future__ import annotations

import pytest

from react_agent.core.context_manager import ContextManager


class TestContextManager:
    def test_add_and_get(self):
        cm = ContextManager(max_tokens=10000)
        cm.add_message({"role": "system", "content": "You are helpful."})
        cm.add_message({"role": "user", "content": "Hi"})
        msgs = cm.get_messages()
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"

    def test_trim_keeps_system_and_recent(self):
        cm = ContextManager(max_tokens=50)  # very small
        cm.add_message({"role": "system", "content": "sys"})
        for i in range(20):
            cm.add_message({"role": "user", "content": f"Message {i} " * 5})
        msgs = cm.get_messages()
        # System message should always be present.
        assert msgs[0]["role"] == "system"
        # Total should be trimmed.
        assert len(msgs) < 22

    def test_clear(self):
        cm = ContextManager()
        cm.add_message({"role": "user", "content": "Hi"})
        cm.clear()
        assert cm.message_count == 0

    def test_truncate_tool_result_short(self):
        result = "short result"
        assert ContextManager.truncate_tool_result(result) == result

    def test_truncate_tool_result_long(self):
        result = "x" * 20000
        truncated = ContextManager.truncate_tool_result(result, max_chars=1000)
        assert len(truncated) < 20000
        assert "truncated" in truncated
