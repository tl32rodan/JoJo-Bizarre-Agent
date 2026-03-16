"""Tests for react_agent.mcp.skill_loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from react_agent.mcp.skill_loader import (
    SkillInfo,
    load_skill_file,
    load_skills_from_paths,
    parse_skill_md,
)


class TestParseSkillMd:
    def test_with_frontmatter(self):
        text = """---
name: filesystem-server
description: Provides sandboxed file operations.
---

## Tools

### ls - List directory contents
### read_file - Read full file contents
"""
        info = parse_skill_md(text)
        assert info.name == "filesystem-server"
        assert info.description == "Provides sandboxed file operations."
        assert "ls" in info.tool_hints
        assert "List directory contents" in info.tool_hints["ls"]
        assert "read_file" in info.tool_hints

    def test_without_frontmatter(self):
        text = """## Tools

### grep_search - Regex search across files
"""
        info = parse_skill_md(text)
        assert info.name == ""
        assert info.description == ""
        assert "grep_search" in info.tool_hints

    def test_empty_text(self):
        info = parse_skill_md("")
        assert info.name == ""
        assert info.body == ""
        assert info.tool_hints == {}


class TestLoadSkillFile:
    def test_load_existing_file(self, tmp_path):
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text(
            "---\nname: test\n---\n### my_tool - Does stuff\n",
            encoding="utf-8",
        )
        info = load_skill_file(skill_file)
        assert info.name == "test"
        assert "my_tool" in info.tool_hints

    def test_load_missing_file(self):
        info = load_skill_file("/nonexistent/SKILL.md")
        assert info.name == ""
        assert info.body == ""


class TestLoadSkillsFromPaths:
    def test_find_skill_in_directory(self, tmp_path):
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text("---\nname: dirtest\n---\nbody\n", encoding="utf-8")
        results = load_skills_from_paths([tmp_path])
        assert len(results) == 1
        assert results[0].name == "dirtest"

    def test_empty_paths(self):
        results = load_skills_from_paths([])
        assert results == []
