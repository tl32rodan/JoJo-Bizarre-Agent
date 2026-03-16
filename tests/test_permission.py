"""Tests for react_agent.services.permission."""

from __future__ import annotations

import pytest

from react_agent.config import PermissionConfig
from react_agent.services.permission import (
    PermissionManager,
    PermissionVerdict,
)


class TestPermissionManager:
    def test_allow_all_mode(self):
        mgr = PermissionManager(PermissionConfig(mode="allow_all"))
        result = mgr.check("anything")
        assert result.verdict == PermissionVerdict.ALLOW

    def test_deny_all_mode(self):
        mgr = PermissionManager(PermissionConfig(mode="deny_all"))
        result = mgr.check("anything")
        assert result.verdict == PermissionVerdict.DENY

    def test_allowed_tools_glob(self):
        mgr = PermissionManager(PermissionConfig(
            mode="ask",
            allowed_tools=["smak:*"],
        ))
        result = mgr.check("smak:semantic_search")
        assert result.verdict == PermissionVerdict.ALLOW

    def test_denied_tools_override(self):
        mgr = PermissionManager(PermissionConfig(
            mode="ask",
            allowed_tools=["*"],
            denied_tools=["delete_file"],
        ))
        result = mgr.check("delete_file")
        assert result.verdict == PermissionVerdict.DENY

    def test_require_confirmation_returns_ask(self):
        mgr = PermissionManager(PermissionConfig(
            mode="ask",
            allowed_tools=["*"],
            require_confirmation=["write_file"],
        ))
        result = mgr.check("write_file")
        assert result.verdict == PermissionVerdict.ASK_USER

    def test_default_ask_mode_unknown_tool(self):
        mgr = PermissionManager(PermissionConfig(
            mode="ask",
            allowed_tools=["read_file"],
        ))
        result = mgr.check("unknown_tool")
        assert result.verdict == PermissionVerdict.ASK_USER

    def test_wildcard_allows_all(self):
        mgr = PermissionManager(PermissionConfig(
            mode="ask",
            allowed_tools=["*"],
        ))
        result = mgr.check("any_tool")
        assert result.verdict == PermissionVerdict.ALLOW

    def test_denied_takes_priority_over_confirmation(self):
        mgr = PermissionManager(PermissionConfig(
            mode="ask",
            denied_tools=["dangerous_tool"],
            require_confirmation=["dangerous_tool"],
        ))
        result = mgr.check("dangerous_tool")
        assert result.verdict == PermissionVerdict.DENY
