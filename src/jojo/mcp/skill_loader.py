"""Load and parse SKILL.md files from MCP server directories."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class SkillInfo:
    name: str = ""
    description: str = ""
    body: str = ""
    tool_hints: dict[str, str] = field(default_factory=dict)


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_TOOL_SECTION_RE = re.compile(r"^###\s+`?(\w+)(?:\(.*?\))?`?\s*[-\u2013\u2014]?\s*(.*)", re.MULTILINE)


def parse_skill_md(text: str) -> SkillInfo:
    name = ""
    description = ""
    body = text

    fm_match = _FRONTMATTER_RE.match(text)
    if fm_match:
        raw_fm = fm_match.group(1)
        body = text[fm_match.end():]
        try:
            fm_data = yaml.safe_load(raw_fm) or {}
        except yaml.YAMLError:
            fm_data = {}
        if isinstance(fm_data, dict):
            name = fm_data.get("name", "")
            description = fm_data.get("description", "")

    tool_hints: dict[str, str] = {}
    for m in _TOOL_SECTION_RE.finditer(body):
        hint = m.group(2).strip()
        if hint:
            tool_hints[m.group(1)] = hint

    return SkillInfo(name=name, description=description, body=body.strip(), tool_hints=tool_hints)


def load_skills_from_paths(paths: list[str | Path]) -> list[SkillInfo]:
    results: list[SkillInfo] = []
    for p in paths:
        p = Path(p)
        if p.is_file() and p.name.upper() == "SKILL.MD":
            text = p.read_text(encoding="utf-8")
            results.append(parse_skill_md(text))
        elif p.is_dir():
            candidate = p / "SKILL.md"
            if candidate.is_file():
                results.append(parse_skill_md(candidate.read_text(encoding="utf-8")))
    return results
