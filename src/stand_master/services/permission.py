"""Permission manager for controlling tool access."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from enum import Enum
from typing import Any

from stand_master.config import PermissionConfig


class PermissionVerdict(Enum):
    ALLOW = "allow"
    DENY = "deny"
    ASK_USER = "ask_user"


@dataclass(frozen=True)
class PermissionResult:
    verdict: PermissionVerdict
    reason: str = ""


class PermissionManager:
    def __init__(self, config: PermissionConfig) -> None:
        self._config = config

    def check(self, tool_name: str, arguments: dict[str, Any] | None = None) -> PermissionResult:
        mode = self._config.mode

        if mode == "allow_all":
            return PermissionResult(verdict=PermissionVerdict.ALLOW)
        if mode == "deny_all":
            return PermissionResult(verdict=PermissionVerdict.DENY, reason="All tools denied.")

        for pattern in self._config.denied_tools:
            if fnmatch.fnmatch(tool_name, pattern):
                return PermissionResult(
                    verdict=PermissionVerdict.DENY,
                    reason=f"Tool '{tool_name}' matches denied pattern '{pattern}'.",
                )

        for name in self._config.require_confirmation:
            if fnmatch.fnmatch(tool_name, name):
                return PermissionResult(
                    verdict=PermissionVerdict.ASK_USER,
                    reason=f"Tool '{tool_name}' requires user confirmation.",
                )

        for pattern in self._config.allowed_tools:
            if fnmatch.fnmatch(tool_name, pattern):
                return PermissionResult(verdict=PermissionVerdict.ALLOW)

        if mode == "ask":
            return PermissionResult(
                verdict=PermissionVerdict.ASK_USER,
                reason=f"Tool '{tool_name}' not explicitly allowed (mode=ask).",
            )

        return PermissionResult(verdict=PermissionVerdict.DENY, reason=f"Tool '{tool_name}' not allowed.")
